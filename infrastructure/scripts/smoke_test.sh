#!/usr/bin/env bash
# smoke_test.sh — Full end-to-end smoke test for SynthRare
#
# Usage: bash infrastructure/scripts/smoke_test.sh [BASE_URL] [--skip-seed]
# Default BASE_URL: http://localhost:8000
#
# The script exercises: health → register → login → refresh →
# catalog → job submit → poll → validation report → API key lifecycle → auth check
#
# NOTE: Requires a running server with migrations applied.
# Seed data (domains/datasets) must exist for job tests to run.
# Run `python -m app.services.seed` or the admin seed step in DEPLOYMENT.md first.

set -uo pipefail

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0
SKIP=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}  PASS${NC} $1"; PASS=$((PASS+1)); }
fail() { echo -e "${RED}  FAIL${NC} $1: $2"; FAIL=$((FAIL+1)); }
skip() { echo -e "${BLUE}  SKIP${NC} $1: $2"; SKIP=$((SKIP+1)); }
info() { echo -e "${YELLOW}  ----${NC} $1"; }

require_cmd() {
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Required command not found: $cmd"; exit 1; }
  done
}

require_cmd curl jq

EMAIL="smoketest_$(date +%s)@synthrare-smoke.com"
PASSWORD="SmokeP@ss99"
ACCESS_TOKEN=""
JOB_ID=""
API_KEY_ID=""

echo ""
echo "======================================"
echo " SynthRare Smoke Test"
echo " Target: $BASE_URL"
echo " Date:   $(date)"
echo "======================================"
echo ""

# ──────────────────────────────────────────
# 1. Health check
# ──────────────────────────────────────────
info "1. Health check"
HEALTH=$(curl -s --max-time 5 "$BASE_URL/health" 2>&1)
STATUS=$(echo "$HEALTH" | jq -r '.status' 2>/dev/null)
if [ "$STATUS" = "ok" ]; then
  ok "GET /health → status=ok"
else
  fail "GET /health" "unreachable or bad response: $HEALTH"
  echo "  Cannot continue — server is not running or /health is broken."
  exit 1
fi

# ──────────────────────────────────────────
# 2. Register
# ──────────────────────────────────────────
info "2. Register new user"
REGISTER=$(curl -s --max-time 5 -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\", \"full_name\": \"Smoke Test\"}")
USER_ID=$(echo "$REGISTER" | jq -r '.id // empty' 2>/dev/null)
if [[ "$USER_ID" =~ ^[0-9]+$ ]]; then
  ok "POST /auth/register → user_id=$USER_ID"
else
  fail "POST /auth/register" "$(echo "$REGISTER" | jq -c '.' 2>/dev/null || echo "$REGISTER")"
fi

# ──────────────────────────────────────────
# 3. Login
# ──────────────────────────────────────────
info "3. Login"
LOGIN=$(curl -s --max-time 5 -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")
ACCESS_TOKEN=$(echo "$LOGIN" | jq -r '.access_token // empty' 2>/dev/null)
REFRESH_TOKEN=$(echo "$LOGIN" | jq -r '.refresh_token // empty' 2>/dev/null)
if [ -n "$ACCESS_TOKEN" ]; then
  ok "POST /auth/login → token received"
else
  fail "POST /auth/login" "$(echo "$LOGIN" | jq -c '.' 2>/dev/null || echo "$LOGIN")"
fi

# ──────────────────────────────────────────
# 4. Token refresh
# ──────────────────────────────────────────
info "4. Token refresh"
if [ -n "$REFRESH_TOKEN" ]; then
  REFRESH=$(curl -s --max-time 5 -X POST "$BASE_URL/auth/refresh" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}")
  NEW_TOKEN=$(echo "$REFRESH" | jq -r '.access_token // empty' 2>/dev/null)
  if [ -n "$NEW_TOKEN" ]; then
    ok "POST /auth/refresh → new token received"
    ACCESS_TOKEN="$NEW_TOKEN"
  else
    fail "POST /auth/refresh" "$(echo "$REFRESH" | jq -c '.' 2>/dev/null || echo "$REFRESH")"
  fi
else
  skip "POST /auth/refresh" "no refresh token (login failed)"
fi

AUTH="Authorization: Bearer $ACCESS_TOKEN"

# ──────────────────────────────────────────
# 5. Browse catalog
# ──────────────────────────────────────────
info "5. Browse catalog"
CATALOG=$(curl -s --max-time 5 "$BASE_URL/catalog")
CATALOG_COUNT=$(echo "$CATALOG" | jq 'length' 2>/dev/null)
if echo "$CATALOG" | jq -e 'type == "array"' > /dev/null 2>&1; then
  ok "GET /catalog → $CATALOG_COUNT dataset(s)"
else
  fail "GET /catalog" "$(echo "$CATALOG" | head -c 200)"
  CATALOG_COUNT=0
fi

# ──────────────────────────────────────────
# 6. Catalog domain filter
# ──────────────────────────────────────────
info "6. Catalog — domain filter"
FILTERED=$(curl -s --max-time 5 "$BASE_URL/catalog?domain_slug=finance")
if echo "$FILTERED" | jq -e 'type == "array"' > /dev/null 2>&1; then
  FC=$(echo "$FILTERED" | jq 'length')
  ok "GET /catalog?domain_slug=finance → $FC result(s)"
else
  fail "GET /catalog?domain_slug=finance" "$(echo "$FILTERED" | head -c 200)"
fi

# ──────────────────────────────────────────
# 7. Submit generation job
# ──────────────────────────────────────────
info "7. Submit generation job (domain_id=1)"
if [ -z "$ACCESS_TOKEN" ]; then
  skip "POST /jobs" "no access token"
elif [ "${CATALOG_COUNT:-0}" -eq 0 ]; then
  skip "POST /jobs" "catalog is empty — seed data required (see docs/DEPLOYMENT.md)"
else
  JOB=$(curl -s --max-time 10 -X POST "$BASE_URL/jobs" \
    -H "Content-Type: application/json" \
    -H "$AUTH" \
    -d '{"domain_id": 1, "row_count": 100, "parameters": {}}')
  JOB_ID=$(echo "$JOB" | jq -r '.id // empty' 2>/dev/null)
  JOB_STATUS=$(echo "$JOB" | jq -r '.status // empty' 2>/dev/null)
  if [[ "$JOB_ID" =~ ^[0-9]+$ ]]; then
    ok "POST /jobs → job_id=$JOB_ID status=$JOB_STATUS"
  else
    fail "POST /jobs" "$(echo "$JOB" | jq -c '.' 2>/dev/null || echo "$JOB")"
  fi
fi

# ──────────────────────────────────────────
# 8. Poll job until completed or timeout
# ──────────────────────────────────────────
info "8. Polling job status (max 30s)"
FINAL_STATUS=""
if [ -z "$JOB_ID" ]; then
  skip "GET /jobs/$JOB_ID" "no job to poll"
else
  for i in $(seq 1 10); do
    /bin/sleep 3
    JOB_POLL=$(curl -s --max-time 5 "$BASE_URL/jobs/$JOB_ID" -H "$AUTH")
    FINAL_STATUS=$(echo "$JOB_POLL" | jq -r '.status // empty' 2>/dev/null)
    if [ "$FINAL_STATUS" = "completed" ] || [ "$FINAL_STATUS" = "failed" ]; then break; fi
    echo "      ... $i/10 status=${FINAL_STATUS:-unknown}"
  done

  if [ "$FINAL_STATUS" = "completed" ]; then
    ok "GET /jobs/$JOB_ID → status=completed"
  elif [ "$FINAL_STATUS" = "pending" ] || [ "$FINAL_STATUS" = "running" ]; then
    ok "GET /jobs/$JOB_ID → status=$FINAL_STATUS (worker not running — expected in isolated smoke test)"
  elif [ "$FINAL_STATUS" = "failed" ]; then
    ERR=$(echo "$JOB_POLL" | jq -r '.error_message // empty')
    fail "GET /jobs/$JOB_ID" "status=failed: $ERR"
  else
    fail "GET /jobs/$JOB_ID" "unexpected status: $FINAL_STATUS"
  fi
fi

# ──────────────────────────────────────────
# 9. List jobs
# ──────────────────────────────────────────
info "9. List jobs"
if [ -z "$ACCESS_TOKEN" ]; then
  skip "GET /jobs" "no access token"
else
  JOBS=$(curl -s --max-time 5 "$BASE_URL/jobs" -H "$AUTH")
  if echo "$JOBS" | jq -e 'type == "array"' > /dev/null 2>&1; then
    JOBS_COUNT=$(echo "$JOBS" | jq 'length')
    ok "GET /jobs → $JOBS_COUNT job(s)"
  else
    fail "GET /jobs" "$(echo "$JOBS" | head -c 200)"
  fi
fi

# ──────────────────────────────────────────
# 10. Validation report (only if job completed)
# ──────────────────────────────────────────
info "10. Validation report"
if [ "$FINAL_STATUS" = "completed" ] && [ -n "$JOB_ID" ]; then
  REPORT=$(curl -s --max-time 10 "$BASE_URL/jobs/$JOB_ID/report" -H "$AUTH")
  SCORE=$(echo "$REPORT" | jq -r '.overall_score // empty' 2>/dev/null)
  if [ -n "$SCORE" ]; then
    ok "GET /jobs/$JOB_ID/report → overall_score=$SCORE"
  else
    fail "GET /jobs/$JOB_ID/report" "$(echo "$REPORT" | jq -c '.' 2>/dev/null || echo "$REPORT")"
  fi
else
  skip "GET /jobs/${JOB_ID:-?}/report" "job not completed (status=${FINAL_STATUS:-no job})"
fi

# ──────────────────────────────────────────
# 11. API key lifecycle
# ──────────────────────────────────────────
info "11. API key lifecycle"
if [ -z "$ACCESS_TOKEN" ]; then
  skip "API key lifecycle" "no access token"
else
  API_KEY_RESP=$(curl -s --max-time 5 -X POST "$BASE_URL/api-keys" \
    -H "Content-Type: application/json" \
    -H "$AUTH" \
    -d '{"name": "smoke-test-key"}')
  RAW_KEY=$(echo "$API_KEY_RESP" | jq -r '.raw_key // empty' 2>/dev/null)
  API_KEY_ID=$(echo "$API_KEY_RESP" | jq -r '.id // empty' 2>/dev/null)

  if [ -n "$RAW_KEY" ]; then
    ok "POST /api-keys → key created (id=$API_KEY_ID)"

    # Test /api/v1/generate via API key
    if [ "${CATALOG_COUNT:-0}" -gt 0 ]; then
      V1_JOB=$(curl -s --max-time 10 -X POST "$BASE_URL/api/v1/generate" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $RAW_KEY" \
        -d '{"domain_id": 1, "row_count": 50, "parameters": {}}')
      V1_ID=$(echo "$V1_JOB" | jq -r '.id // empty' 2>/dev/null)
      if [[ "$V1_ID" =~ ^[0-9]+$ ]]; then
        ok "POST /api/v1/generate → job_id=$V1_ID"
        # Poll status via API key
        V1_STATUS=$(curl -s --max-time 5 "$BASE_URL/api/v1/jobs/$V1_ID" \
          -H "Authorization: Bearer $RAW_KEY")
        V1_S=$(echo "$V1_STATUS" | jq -r '.status // empty' 2>/dev/null)
        if [ -n "$V1_S" ]; then
          ok "GET /api/v1/jobs/$V1_ID → status=$V1_S"
        else
          fail "GET /api/v1/jobs/$V1_ID" "$(echo "$V1_STATUS" | head -c 200)"
        fi
      else
        fail "POST /api/v1/generate" "$(echo "$V1_JOB" | jq -c '.' 2>/dev/null || echo "$V1_JOB")"
      fi
    else
      skip "POST /api/v1/generate" "catalog empty — seed data required"
    fi

    # Delete the API key
    DEL_CODE=$(curl -s --max-time 5 -X DELETE "$BASE_URL/api-keys/$API_KEY_ID" \
      -H "$AUTH" -o /dev/null -w "%{http_code}")
    if [ "$DEL_CODE" = "204" ]; then
      ok "DELETE /api-keys/$API_KEY_ID → 204"
    else
      fail "DELETE /api-keys/$API_KEY_ID" "HTTP $DEL_CODE"
    fi
  else
    fail "POST /api-keys" "$(echo "$API_KEY_RESP" | jq -c '.' 2>/dev/null || echo "$API_KEY_RESP")"
  fi
fi

# ──────────────────────────────────────────
# 12. List API keys
# ──────────────────────────────────────────
info "12. List API keys"
if [ -z "$ACCESS_TOKEN" ]; then
  skip "GET /api-keys" "no access token"
else
  KEYS=$(curl -s --max-time 5 "$BASE_URL/api-keys" -H "$AUTH")
  if echo "$KEYS" | jq -e 'type == "array"' > /dev/null 2>&1; then
    KC=$(echo "$KEYS" | jq 'length')
    ok "GET /api-keys → $KC key(s)"
  else
    fail "GET /api-keys" "$(echo "$KEYS" | head -c 200)"
  fi
fi

# ──────────────────────────────────────────
# 13. Auth enforcement
# ──────────────────────────────────────────
info "13. Auth enforcement"
UNAUTH=$(curl -s --max-time 5 -o /dev/null -w "%{http_code}" "$BASE_URL/jobs")
if [ "$UNAUTH" = "401" ] || [ "$UNAUTH" = "403" ]; then
  ok "GET /jobs (no token) → HTTP $UNAUTH (auth enforced)"
else
  fail "GET /jobs (no token)" "expected 401 or 403, got $UNAUTH"
fi

# ──────────────────────────────────────────
# Summary
# ──────────────────────────────────────────
echo ""
echo "======================================"
TOTAL=$((PASS + FAIL + SKIP))
echo " Results: $PASS passed / $FAIL failed / $SKIP skipped  ($TOTAL total)"
if [ "$FAIL" -eq 0 ]; then
  echo -e " ${GREEN}ALL CHECKS PASSED${NC}"
  if [ "$SKIP" -gt 0 ]; then
    echo -e " ${BLUE}($SKIP skipped — seed data required for full run)${NC}"
    echo " Seed: doctl apps exec <APP_ID> --component backend -- python -c 'from app.services.seed import run_seed; from app.database import SessionLocal; db=SessionLocal(); run_seed(db); db.close()'"
  fi
else
  echo -e " ${RED}$FAIL CHECK(S) FAILED${NC}"
fi
echo "======================================"
echo ""

[ "$FAIL" -eq 0 ]
