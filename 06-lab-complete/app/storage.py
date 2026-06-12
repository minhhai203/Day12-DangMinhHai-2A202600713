"""Redis-backed storage shared by every application instance."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import redis

from app.config import settings


class RedisStorage:
    def __init__(self) -> None:
        self.client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout_seconds,
            socket_timeout=settings.redis_socket_timeout_seconds,
        )

    def ping(self) -> bool:
        return bool(self.client.ping())

    @staticmethod
    def _history_key(session_id: str) -> str:
        return f"session:{session_id}:history"

    @staticmethod
    def _owner_key(session_id: str) -> str:
        return f"session:{session_id}:owner"

    def session_exists(self, session_id: str) -> bool:
        return bool(self.client.exists(self._owner_key(session_id)))

    def assert_session_owner(self, session_id: str, user_id: str) -> None:
        owner = self.client.get(self._owner_key(session_id))
        if owner and owner != user_id:
            raise PermissionError("Session belongs to another user")

    def append_message(self, session_id: str, user_id: str, role: str, content: str) -> None:
        message = json.dumps(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        )
        history_key = self._history_key(session_id)
        owner_key = self._owner_key(session_id)
        with self.client.pipeline(transaction=True) as pipeline:
            pipeline.set(owner_key, user_id, ex=settings.session_ttl_seconds)
            pipeline.rpush(history_key, message)
            pipeline.ltrim(history_key, -settings.max_history_messages, -1)
            pipeline.expire(history_key, settings.session_ttl_seconds)
            pipeline.execute()

    def get_history(self, session_id: str, user_id: str) -> list[dict]:
        self.assert_session_owner(session_id, user_id)
        messages = self.client.lrange(self._history_key(session_id), 0, -1)
        return [json.loads(message) for message in messages]

    def delete_session(self, session_id: str, user_id: str) -> bool:
        self.assert_session_owner(session_id, user_id)
        deleted = self.client.delete(
            self._history_key(session_id),
            self._owner_key(session_id),
        )
        return deleted > 0


storage = RedisStorage()
