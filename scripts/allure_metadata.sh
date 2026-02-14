#!/bin/bash

# Allure metadata: executor (build name, report title) and environment.
# buildOrder + type fix the dashboard "UNKNOWN" display; Allure only recognizes
# type: jenkins|bamboo|teamcity|gitlab|github|circleci|bitbucket|azure.

CURRENT_TIME=$(date +"%Y-%m-%d %H:%M:%S")
# buildOrder: integer for trend graphs; use epoch so each run is unique
BUILD_ORDER=$(date +%s)
RESULTS_DIR="allure-results"

mkdir -p "$RESULTS_DIR"

cat <<EOF > "$RESULTS_DIR/executor.json"
{
  "name": "Ahmet Demir",
  "type": "github",
  "buildOrder": $BUILD_ORDER,
  "buildName": "Regression Run - $CURRENT_TIME",
  "reportName": "Mobile QA Regression Report",
  "buildUrl": "http://localhost:1234"
}
EOF

# Environment Info
cat <<EOF > "$RESULTS_DIR/environment.properties"
Execution_Date=$CURRENT_TIME
Browser=IOS Simulator
Device=iPhone 17
Framework=Maestro_V2.0
EOF