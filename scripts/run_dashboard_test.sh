#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

# .env varsa yükle
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

mkdir -p allure-results/maestro-dashboard
maestro test \
  -e ENGINEER_ID="${ENGINEER_ID:-}" \
  -e SECURITY_TOKEN="${SECURITY_TOKEN:-}" \
  --format junit --output allure-results/dashboard_report.xml \
  --test-output-dir=allure-results/maestro-dashboard \
  .maestro/flows/dashboard_test.yaml "$@"

