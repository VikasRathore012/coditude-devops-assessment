#!/usr/bin/env python3
"""Smoke-test actual Next.js standalone output after npm run build (no AWS)."""
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request

root = Path(__file__).resolve().parents[1] / 'apps/frontend'
standalone = root / '.next/standalone'
for manifest in (standalone / '.next').rglob('*.json'):
    json.loads(manifest.read_text())
shutil.copytree(root / '.next/static', standalone / '.next/static', dirs_exist_ok=True)
with socket.socket() as probe:
    probe.bind(('127.0.0.1', 0))
    port = probe.getsockname()[1]
env = dict(os.environ, HOSTNAME='127.0.0.1', PORT=str(port), NEXT_TELEMETRY_DISABLED='1')
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
base = f'http://127.0.0.1:{port}'
with tempfile.TemporaryFile(mode='w+') as logs:
    process = subprocess.Popen(['node', str(standalone / 'server.js')], env=env, stdout=logs, stderr=logs)
    try:
        for _ in range(60):
            if process.poll() is not None:
                logs.seek(0)
                raise RuntimeError(logs.read())
            try:
                with opener.open(base + '/health', timeout=1) as response:
                    assert response.status == 200 and json.load(response) == {'status': 'ok'}
                break
            except OSError:
                time.sleep(0.25)
        else:
            raise RuntimeError('Frontend did not become ready')
        with opener.open(base + '/', timeout=5) as response:
            page = response.read().decode()
            assert response.status == 200 and 'Deployment check' in page
        asset = re.search(r'src="(/_next/static/[^"?]+)', page)
        assert asset, 'No frontend JavaScript asset found'
        with opener.open(base + asset.group(1), timeout=5) as response:
            assert response.status == 200 and len(response.read()) > 0
        print('PASS: standalone frontend /, /health, and JavaScript asset return HTTP 200')
    finally:
        process.terminate()
        process.wait(timeout=10)
