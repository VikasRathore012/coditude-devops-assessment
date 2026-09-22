#!/bin/bash
set -euo pipefail
for service in assessment-frontend assessment-backend; do
  if systemctl cat "$service" >/dev/null 2>&1; then systemctl stop "$service"; fi
done
