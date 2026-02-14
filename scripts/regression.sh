#!/bin/bash
for script in ./scripts/*_test.sh; do
  echo "Running $script..."
  bash "$script"
done