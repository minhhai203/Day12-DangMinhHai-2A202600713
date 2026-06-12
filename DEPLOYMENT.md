# Deployment Information

## Railway Project

- Project: `VinUni_lab12_2A202600713`
- Environment: `production`
- Service: `VinUni_lab12_2A202600713`
- Public URL: <https://vinunilab122a202600713-production.up.railway.app>

The local Railway project link is configured in `06-lab-complete`. The app and managed
Redis service are running in the Railway `production` environment.

```bash
cd 06-lab-complete
railway status
```

## Required Railway Services

1. Application service built successfully from `06-lab-complete/Dockerfile`.
2. Railway Redis service connected through the `${{Redis.REDIS_URL}}` reference.

## Environment Variables

```text
ENVIRONMENT=production
AGENT_API_KEY=<long random secret>
REDIS_URL=<Railway Redis reference>
RATE_LIMIT_PER_MINUTE=10
MONTHLY_BUDGET_USD=10.0
LLM_MODEL=mock-llm
```

No paid AI provider is required because this lab uses the included mock LLM.

## Redeploy Commands

```bash
cd 06-lab-complete
railway up
railway domain
```

## Test Commands

Set `URL` to the public domain and use the deployment API key.

```bash
curl "$URL/health"
curl "$URL/ready"
```

Authentication must be required:

```bash
curl -i -X POST "$URL/ask" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
# Expected: 401
```

Authenticated request:

```bash
curl -X POST "$URL/ask" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
# Expected: 200
```

Full integration test:

```bash
cd 06-lab-complete
python test_integration.py
```

## Local Verification

The application was verified locally against Redis:

```text
health=200
ready=200
missing API key=401
invalid input=422
conversation history=passed
rate limit=429 after 10 requests
monthly cost guard=402 at $10
graceful shutdown=passed
```

The same integration suite passed against the Railway public URL on June 12, 2026.

## Screenshots

- [Deployment and API verification](screenshots/deployment-terminal.png)
- [Cloud integration test results](screenshots/cloud-integration-tests.png)
