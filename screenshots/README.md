# Deployment Screenshots

Public service:

<https://vinunilab122a202600713-production.up.railway.app>

## Deployment Verification

`deployment-terminal.png` shows:

- Railway application and Redis services in `SUCCESS` state.
- Public Railway URL.
- Health and readiness responses.
- `401` response without an API key.
- Successful authenticated agent response with `HTTP 200`.

## Cloud Integration Tests

`cloud-integration-tests.png` shows the complete public deployment test suite:

- Health and readiness checks.
- Authentication and input validation.
- Multi-turn conversation history stored in Redis.
- History endpoint.
- Rate limiting returning `429` after 10 requests.

The screenshots were captured on June 12, 2026. API key values are not displayed.
