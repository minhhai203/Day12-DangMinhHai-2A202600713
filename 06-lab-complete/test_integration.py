"""End-to-end checks for the Railway deployment or a local server."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Optional


RAILWAY_URL = "https://vinunilab122a202600713-production.up.railway.app"
RAILWAY_SERVICE_ID = "0c3a8fdf-7d35-4b5c-9f05-a00121608420"
BASE_URL = os.getenv("BASE_URL", RAILWAY_URL).rstrip("/")


def resolve_api_key() -> str:
    configured_key = os.getenv("AGENT_API_KEY")
    if configured_key:
        return configured_key
    if BASE_URL != RAILWAY_URL:
        return "day12-local-secret"

    try:
        result = subprocess.run(
            [
                "railway",
                "variables",
                "--service",
                RAILWAY_SERVICE_ID,
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return json.loads(result.stdout)["AGENT_API_KEY"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError, subprocess.SubprocessError):
        print(
            "ERROR: Cannot read AGENT_API_KEY from Railway.\n"
            "Run `railway login`, or set AGENT_API_KEY before running this test.",
            file=sys.stderr,
        )
        raise SystemExit(2)


API_KEY = resolve_api_key()


def request(
    method: str,
    path: str,
    body: Optional[dict] = None,
    authenticated: bool = False,
) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if authenticated:
        headers["X-API-Key"] = API_KEY
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())
    except urllib.error.URLError as exc:
        print(
            f"ERROR: Cannot connect to {BASE_URL}: {exc.reason}\n"
            "For local testing, start the stack with `docker compose up -d`.\n"
            "For Railway testing, omit BASE_URL or set it to the public URL.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def assert_status(actual: int, expected: int, label: str) -> None:
    assert actual == expected, f"{label}: expected {expected}, got {actual}"
    print(f"PASS  {label} ({actual})")


print(f"Testing: {BASE_URL}\n")

health_status, _ = request("GET", "/health")
assert_status(health_status, 200, "health")

ready_status, _ = request("GET", "/ready")
assert_status(ready_status, 200, "readiness")

unauthorized_status, _ = request(
    "POST",
    "/ask",
    {"user_id": "unauthorized", "question": "Hello"},
)
assert_status(unauthorized_status, 401, "authentication required")

invalid_status, _ = request(
    "POST",
    "/ask",
    {"user_id": "invalid user id", "question": ""},
    authenticated=True,
)
assert_status(invalid_status, 422, "input validation")

run_id = uuid.uuid4().hex[:10]
user_id = f"conversation-{run_id}"
first_status, first = request(
    "POST",
    "/ask",
    {"user_id": user_id, "question": "My first question is about Docker"},
    authenticated=True,
)
assert_status(first_status, 200, "first conversation turn")

second_status, second = request(
    "POST",
    "/ask",
    {
        "user_id": user_id,
        "session_id": first["session_id"],
        "question": "What did I ask previously?",
    },
    authenticated=True,
)
assert_status(second_status, 200, "second conversation turn")
assert "Docker" in second["answer"], "conversation context was not preserved"
assert second["history_count"] == 4, "expected two user and two assistant messages"
print("PASS  Redis conversation history")

history_path = (
    f"/sessions/{first['session_id']}/history?"
    + urllib.parse.urlencode({"user_id": user_id})
)
history_status, history = request("GET", history_path, authenticated=True)
assert_status(history_status, 200, "history endpoint")
assert len(history["messages"]) == 4

rate_user = f"rate-limit-{run_id}"
statuses = []
for index in range(11):
    status, _ = request(
        "POST",
        "/ask",
        {"user_id": rate_user, "question": f"Request {index}"},
        authenticated=True,
    )
    statuses.append(status)
assert statuses[:10] == [200] * 10, statuses
assert statuses[10] == 429, statuses
print("PASS  rate limit returns 429 after 10 requests")

print("\nAll integration tests passed.")
