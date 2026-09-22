#!/bin/bash
set -euo pipefail
for attempt in $(seq 1 20); do
  if curl -fsS --max-time 5 http://127.0.0.1:3000/health >/dev/null && \
     curl -fsS --max-time 5 http://127.0.0.1:8000/api/ready >/dev/null; then exit 0; fi
  sleep 3
done
exit 1
