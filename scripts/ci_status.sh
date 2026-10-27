#!/usr/bin/env bash
# Print the status of a workflow run and each of its steps. Usage: ci_status.sh <run-id>
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
gh run view "$1" -R SalatielBM22/penang-xnu-build --json status,conclusion,jobs \
  --jq '"run: \(.status) \(.conclusion // "")", (.jobs[0].steps[] | "  \(.name): \(.status) \(.conclusion // "")")'
