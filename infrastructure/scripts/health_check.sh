#!/bin/bash
set -e

API_URL="${1:-http://localhost:8000}"

echo "Checking $API_URL/health ..."
response=$(curl -sf "$API_URL/health")
status=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")

if [ "$status" = "ok" ]; then
  echo "Health check passed: $response"
  exit 0
else
  echo "Health check FAILED: $response"
  exit 1
fi
