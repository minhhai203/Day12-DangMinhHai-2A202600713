# Lab 12 - Complete Production Agent

Production-ready FastAPI agent combining configuration, Docker, API security, Redis-backed
state, reliability probes, graceful shutdown, load balancing, and Railway deployment.

## Architecture

```text
Client -> Nginx -> Agent 1 --+
                -> Agent 2 --+-> Redis
                -> Agent 3 --+
```

Redis stores conversation history, rate-limit windows, and monthly cost usage so any agent
instance can serve the next request.

## Requirements

- Docker and Docker Compose
- Or Python 3.11+ and a local Redis server

No OpenAI key or paid provider is required. The app uses `utils/mock_llm.py`.

## Run With Docker

```bash
cp .env.example .env
docker compose up --build --scale agent=3
```

The service is available through Nginx at `http://localhost:8000`.

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Send a question:

```bash
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: replace-with-a-long-random-secret" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"student","question":"What is Docker?"}'
```

Use the returned `session_id` in the next request:

```bash
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: replace-with-a-long-random-secret" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"student","session_id":"SESSION_ID","question":"What did I ask previously?"}'
```

## Run Without Docker

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

REDIS_URL=redis://localhost:6379/0 \
AGENT_API_KEY=day12-local-secret \
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Validate

With the API running:

```bash
python check_production_ready.py
python test_integration.py
```

By default, `test_integration.py` tests the deployed Railway service and reads its API key
from the linked Railway project. For local testing:

```bash
BASE_URL=http://localhost:8000 \
AGENT_API_KEY=day12-local-secret \
python test_integration.py
```

The integration test verifies `200`, `401`, `422`, conversation history, and `429`.

## Production Defaults

| Setting | Default |
|---|---|
| Rate limit | 10 requests/minute/user |
| Cost budget | 10 USD/month/user |
| Session TTL | 24 hours |
| Maximum history | 20 messages |
| Graceful shutdown timeout | 30 seconds |

## Railway

The directory is linked to project `VinUni_lab12_2A202600713`.

1. Add a Redis service in Railway.
2. Expose its connection as `REDIS_URL`.
3. Set `ENVIRONMENT=production` and a strong `AGENT_API_KEY`.
4. Run `railway up`.
5. Generate a domain and run `test_integration.py` against it.

See the repository-level `DEPLOYMENT.md` for exact commands.
