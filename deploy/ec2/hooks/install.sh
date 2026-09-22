#!/bin/bash
set -euo pipefail
release="/opt/assessment/releases/${DEPLOYMENT_ID:?}"
mv /opt/assessment/incoming "$release"
python3.12 -m venv "$release/venv"
"$release/venv/bin/python" -m pip install --disable-pip-version-check -r "$release/backend/requirements.txt"
mkdir -p "$release/frontend/.next/cache" /var/log/assessment
chown -R assessment:assessment "$release" /var/log/assessment
cp "$release"/systemd/*.service /etc/systemd/system/
ln -sfn "$release" /opt/assessment/current
systemctl daemon-reload
