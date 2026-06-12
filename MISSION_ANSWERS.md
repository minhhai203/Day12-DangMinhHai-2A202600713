# Day 12 Lab - Mission Answers

**Student:** Dang Minh Hai  
**Student ID:** 2A202600713

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

1. API key is hardcoded in source code and can be leaked through Git history.
2. Port `8000` is hardcoded instead of being read from `PORT`.
3. Debug mode is enabled directly in code.
4. There is no liveness health endpoint.
5. There is no readiness endpoint for dependencies.
6. The application does not handle graceful shutdown.
7. Logging uses unstructured output instead of JSON.
8. Configuration is mixed with application logic.

### Exercise 1.2: Basic version

The basic application can answer `POST /ask`, but being reachable on localhost does not
make it production-ready. It lacks external configuration, operational probes, secure
secret handling, and controlled shutdown.

### Exercise 1.3: Comparison

| Feature | Develop | Production | Why important? |
|---|---|---|---|
| Configuration | Hardcoded | Environment variables | The same image can run in development, staging, and production |
| Secrets | Stored in code | Injected at runtime | Prevents credentials from entering Git history |
| Port | Fixed at `8000` | Read from `PORT` | Cloud platforms assign ports dynamically |
| Health check | Missing | `GET /health` | Orchestrators can detect and restart unhealthy processes |
| Readiness | Missing | `GET /ready` | Traffic is only routed when dependencies are available |
| Logging | `print()` | Structured JSON events | Logs can be searched and processed by cloud tooling |
| Shutdown | Abrupt | Uvicorn graceful shutdown | In-flight requests can finish before the process exits |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. Base image: `python:3.11`. It contains Linux, Python 3.11, and the Python runtime tools.
2. Working directory: `/app`.
3. `requirements.txt` is copied before application code so Docker can reuse the dependency
   installation layer when only source code changes.
4. `CMD` supplies the default container command and can be replaced at `docker run` time.
   `ENTRYPOINT` defines the main executable and is harder to replace.

### Exercise 2.2: Basic image

Build command from repository root:

```bash
docker build -f 02-docker/develop/Dockerfile -t agent-develop .
```

The locally cached basic image is `1.67 GB`. The earlier failure happened because the
build context was `02-docker/develop`, so Docker could not access root-level
`utils/mock_llm.py`.

### Exercise 2.3: Multi-stage build

The builder stage installs dependencies and includes compilation tools. The runtime stage
starts again from `python:3.11-slim`, copies only installed packages and application code,
and runs as a non-root user. This removes compilers and build-only files from the final
image. The final Dockerfile also includes a health check.

Local measurement of the final image was temporarily blocked by Docker Hub's anonymous
pull limit (`429 Too Many Requests`). The Dockerfile enforces the required slim,
multi-stage structure and the image can be measured with:

```bash
cd 06-lab-complete
docker compose build
docker image ls 06-lab-complete-agent
```

### Exercise 2.4: Docker Compose architecture

```text
Client -> Nginx :8000 -> Agent instances :8000 -> Redis :6379
```

`nginx` is the public reverse proxy and load balancer. Agent containers do not publish a
host port directly. Redis stores conversation history, sliding-window rate data, and
monthly cost data shared by all agent instances.

## Part 3: Cloud Deployment

### Exercise 3.1: Railway

Railway project: `VinUni_lab12_2A202600713`  
Environment: `production`
Public URL: <https://vinunilab122a202600713-production.up.railway.app>

The repository includes `06-lab-complete/railway.toml`, a production Dockerfile, and a
health check. Railway CLI is linked to the project, a managed Redis service is connected
through `REDIS_URL`, and the cloud deployment passed the integration suite.

### Exercise 3.2: Railway vs Render

| Topic | Railway | Render |
|---|---|---|
| Config file | `railway.toml` | `render.yaml` |
| Deployment model | Build and deploy one linked service | Blueprint can describe multiple services |
| Environment variables | CLI or dashboard | `envVars` in blueprint/dashboard |
| Start command | `[deploy].startCommand` | `startCommand` or Docker runtime |
| Health check | `healthcheckPath` | `healthCheckPath` |

### Exercise 3.3: Cloud Run

`cloudbuild.yaml` describes the CI/CD build and deployment steps. `service.yaml` describes
the Cloud Run runtime service. Cloud Run is a stronger production option when automatic
scaling, revision management, and integration with Google Cloud are required.

## Part 4: API Security

### Exercise 4.1: API key

`X-API-Key` is read by FastAPI's `APIKeyHeader` dependency. Missing or incorrect keys
return `401`. Rotation is performed by changing `AGENT_API_KEY` in the deployment
environment and restarting/redeploying the service, without editing source code.

Verified result:

```text
PASS authentication required (401)
```

### Exercise 4.2: JWT

JWT authentication is demonstrated in `04-api-gateway/production/auth.py`. The user first
exchanges credentials for a signed token, then sends `Authorization: Bearer <token>`.
The final project uses API key authentication because that is the required submission
interface.

### Exercise 4.3: Rate limiting

The final app uses a Redis sorted set as a sliding 60-second window. Old timestamps are
removed, active requests are counted, and the next member is recorded with a TTL. The
default limit is `10 requests/minute per user`. Because state is in Redis, all replicas
enforce the same limit.

Verified result:

```text
PASS rate limit returns 429 after 10 requests
```

### Exercise 4.4: Cost guard

Each user has a Redis key in the form `cost:<user_id>:<YYYY-MM>`. A Lua script atomically
checks the current cost and records estimated request cost. The default budget is
`$10/month per user`; exceeding it returns `402 Payment Required`.

Verified result:

```text
HTTP 402
{"detail":{"error":"Monthly budget exceeded","used_usd":10.0,"budget_usd":10.0}}
```

## Part 5: Scaling and Reliability

### Exercise 5.1: Health and readiness

- `GET /health` is a liveness probe and returns process metadata without depending on Redis.
- `GET /ready` checks Redis and returns `503` when shared storage is unavailable.

Verified results:

```text
PASS health (200)
PASS readiness (200)
```

### Exercise 5.2: Graceful shutdown

Uvicorn handles `SIGTERM`, stops accepting new traffic, waits up to 30 seconds for active
requests, and then runs the FastAPI lifespan shutdown block. The shutdown log was:

```text
Waiting for application shutdown.
{"event":"graceful_shutdown","in_flight_requests":0}
Application shutdown complete.
```

### Exercise 5.3: Stateless design

Conversation history is stored as Redis lists. Session ownership, rate windows, and monthly
cost are also stored in Redis. No business state required by a later request is stored only
inside an agent process.

### Exercise 5.4: Load balancing

The stack can be scaled with:

```bash
docker compose up --build --scale agent=3
```

Nginx uses `least_conn` to distribute requests across healthy agent containers.

### Exercise 5.5: Stateless test

The integration test creates a session, sends a second request with the same session ID,
and reads the complete history from Redis:

```text
PASS first conversation turn (200)
PASS second conversation turn (200)
PASS Redis conversation history
PASS history endpoint (200)
```

## Final Project Validation

```text
Production readiness: 17/17 checks passed
Local integration tests: all passed
Railway integration tests: all passed
Railway monthly budget test: HTTP 402
```

Run the same checks with:

```bash
cd 06-lab-complete
python check_production_ready.py
python test_integration.py
```
