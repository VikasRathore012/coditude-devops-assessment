#!/bin/bash
set -euo pipefail
systemctl enable --now assessment-backend assessment-frontend
systemctl restart assessment-backend assessment-frontend
