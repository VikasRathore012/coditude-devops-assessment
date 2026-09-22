# Scope, assumptions and remaining validation

This is a source-code assessment submission, not a completed AWS deployment.

- No AWS account, resources, live pipeline execution or live rollback was used.
- CloudFormation linting validates schema/intrinsics; it does not establish IAM
  sufficiency, quotas, regional versions, service readiness or successful creation.
- A real certificate, DNS hostname, repository identity, OIDC provider, optional
  CodeConnections connection, environment protections and governed infrastructure
  execution role are external configuration prerequisites.
- The DB app login must be bootstrapped once; creating a secret alone is insufficient.
- One deployment driver must own each target. App and infra releases require
  coordination; no shared distributed release lock is implemented.
- Dev/staging deliberately use single-AZ RDS and one NAT. Only prod enables
  the full two-AZ DB/NAT configuration.
- The native EC2 sample installs runtime dependencies at bootstrap/deployment time.
  Prefer approved AMIs and a prebuilt, scanned Python wheelhouse for production.
- The application is a connectivity probe, not a business application or load-test
  benchmark. It does not claim application auth, schema migrations or pooling.
- EC2 log/release cleanup, rotating the dedicated DB credential, an external uptime
  probe, blocking vulnerability gates, WAF and regional DR are future production
  controls; their absence is explicitly documented.
- Container and Compose execution require Docker. Check `docs/validation.md` for
  whether these were executed in the authoring environment.

All executable template logic is included. Intentional environment placeholders
must be replaced only for live deployment; they do not prevent offline review.
