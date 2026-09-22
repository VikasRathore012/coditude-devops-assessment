# Security approach

- ALB is the only public application entrypoint. HTTP redirects to HTTPS with an
  ACM certificate. EC2 and ECS receive no public IPs; no SSH port is opened.
- Security groups permit ALB-to-application traffic only on 3000/8000 and DB access
  from the application group only on 5432. DB subnets have no internet route.
- RDS storage, ECR images and S3 artifacts are encrypted. S3 blocks public access,
  enforces TLS and versions objects. RDS backups/snapshots have retention controls.
- `rds.force_ssl=1` and client `sslmode=verify-full` validate the RDS server using
  the AWS RDS trust bundle. Local Compose's explicit APP_ENV=local is the sole
  plaintext-DB exception.
- RDS manages the master secret. A separate application secret holds a restricted
  database login. ECS frontend cannot fetch it; ECS backend can fetch exactly
  that secret. EC2 shares a host instance role between its two processes; this
  trade-off is documented rather than claiming process-level IAM isolation.
- The one-time bootstrap CodeBuild role can read both DB secrets; normal build,
  application and release roles cannot read the master secret. Delete the
  bootstrap stack after initialization. Do not expose passwords in command logs.
- Runtime credentials refresh every 60 seconds. Automatic application-secret
  rotation is **not configured**. A future rotation workflow must update both
  PostgreSQL and Secrets Manager coherently, test connections, and recover on
  failure. Do not rotate only the secret value. RDS master-secret management is
  separate from application-login rotation.
- ECS task roles and execution roles are distinct. Container processes run as
  non-root users. EC2 enforces IMDSv2 and uses SSM instead of SSH; services run as
  the unprivileged assessment account with systemd restrictions.
- GitHub OIDC trust matches the exact repository/environment and audience. Role
  separation plus explicit CFN write deny protects infra from application releases.
  RegisterTaskDefinition and authorization-token APIs require wildcard resources;
  iam:PassRole and service updates are restricted to supplied exact role/service ARNs.
- GitHub Actions are pinned to verified commit SHAs. npm has a lockfile and Python
  application dependencies have exact versions. Docker base images are version
  tags, not immutable digest pins; resolve and approve base digests for production.
  Dependabot is included to surface dependency updates. ECR scan-on-push provides
  findings but is not a blocking vulnerability gate in this assessment.

## Account governance outside this repository

Account/SCP/permission-boundary policy, organization CloudTrail, GuardDuty,
Security Hub, central log retention and incident escalation depend on the target
organization. The deployment runbook requires a pre-existing governed
CloudFormation execution role rather than inventing an account administrator.
Review that role's effective privileges before enabling any infrastructure workflow.

WAF rules, identity authentication, rate limits and business authorization are not
included in the public connectivity-only demonstration. Add them before exposing
real business endpoints or personal data. Do not describe this repository as a
security-audited or live production-certified system.
