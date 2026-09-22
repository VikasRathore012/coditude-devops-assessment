# Local validation evidence

Validation date: 2026-09-22. No AWS deployment was attempted.

| Check | Result |
|---|---|
| CloudFormation lint, all seven templates | PASS, no warnings/errors |
| Python tests | PASS: 7 tests; 2 third-party deprecation warnings |
| YAML/JSON/Python/shell and deployment contract checks | PASS |
| Next.js 16.3.5 production build (Turbopack) | PASS |
| Actual standalone server: page, health, JS asset | PASS: HTTP 200 |
| npm production dependency audit | 0 reported vulnerabilities at validation time |
| Container builds / Docker Compose | NOT RUN: Docker unavailable in authoring environment |
| PostgreSQL end-to-end connectivity | NOT RUN against a live DB; readiness success/failure paths unit-tested |
| AWS provisioning, live pipelines, live rollback and AZ failover | NOT RUN: outside assessment requirement |

## Environment

- Python 3.12; Node.js v24.19.0 in authoring runtime. Deployment/CI specifies Node.js 22; that runtime has not been executed here.
- cfn-lint 1.57.0; pytest 9.1.1.
- Third-party warnings concern Starlette TestClient/httpx and an AnyIO alias; they do not fail the seven tests.
- Build initially used webpack and exposed an invalid generated prefetch manifest at runtime. The final package uses Next.js default Turbopack; both its build and actual standalone HTTP checks passed. The checked-in smoke script guards this failure mode.
- A code review identified empty IAM inline policies and missing CodeBuild bucket metadata permissions; both were corrected before the final lint run.

## Captured final checks

### CloudFormation lint

```text
(no warnings or errors)
```

### Repository contracts

```text
PASS: templates/YAML/JSON/Python/shell parse; app/infra path separation and release verification contracts
```

### Python tests

```text
.......                                                                  [100%]
=============================== warnings summary ===============================
../../../../root/.local/lib/python3.12/site-packages/fastapi/testclient.py:1
  /root/.local/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

../../../../root/.local/lib/python3.12/site-packages/starlette/testclient.py:53
  /root/.local/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
7 passed, 2 warnings in 1.02s
```

### Frontend standalone smoke

```text
PASS: standalone frontend /, /health, and JavaScript asset return HTTP 200
```
