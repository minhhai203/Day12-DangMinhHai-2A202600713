#!/usr/bin/env bash
set -euo pipefail

BASE_URL="https://vinunilab122a202600713-production.up.railway.app"
SERVICE_ID="0c3a8fdf-7d35-4b5c-9f05-a00121608420"

clear
printf "DAY 12 PRODUCTION DEPLOYMENT VERIFICATION\n\n"
printf "Public URL: %s\n" "$BASE_URL"
printf "Verified: 2026-06-12\n\n"

printf "=== Railway Services ===\n"
railway service list --json |
  jq -r '.[] | [.name, .status, ((.replicas.running | tostring) + " replica running")] | @tsv'

printf "\n=== Health Check ===\n"
curl -sS "$BASE_URL/health" | jq .

printf "\n=== Readiness Check ===\n"
curl -sS "$BASE_URL/ready" | jq .

printf "\n=== Authentication Required ===\n"
curl -sS -o /tmp/day12-no-key.json -w "HTTP %{http_code}\n" \
  -X POST "$BASE_URL/ask" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"screenshot-no-key","question":"Hello"}'
jq . /tmp/day12-no-key.json

printf "\n=== Authenticated Agent Request ===\n"
API_KEY="$(
  railway variables --service "$SERVICE_ID" --json |
    jq -r '.AGENT_API_KEY'
)"
curl -sS -o /tmp/day12-auth.json -w "HTTP %{http_code}\n" \
  -X POST "$BASE_URL/ask" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"screenshot-test","question":"What is Docker?"}'
jq '{user_id, session_id, question, answer, history_count, served_by, model}' \
  /tmp/day12-auth.json

printf "\nALL DEPLOYMENT CHECKS COMPLETED\n"
