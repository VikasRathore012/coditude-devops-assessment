# Rollback and recovery

## ECS application release

Each build uses a commit-SHA tag in immutable ECR repositories and deploys by image
digest. The script records both old task-definition ARNs, registers new revisions,
updates services and waits for stability. It checks the exact revision because an
ECS circuit-breaker rollback can otherwise look like a successful stable service.

If either service or the HTTPS readiness check fails, it restores both old task
revisions and waits for that rollback. Frontend/backend changes must remain
backward compatible during the brief rolling-deployment overlap; this is not an
atomic distributed transaction.

For an operator rollback, download the corresponding release manifest from
GitHub build artifacts or `s3://ARTIFACT_BUCKET/releases/COMMIT/ecs-release.json`:

```bash
python scripts/rollback.py --runtime coditude-dev-ecs --manifest release.json
```

The manifest's `previous` field is the rollback target. Keep tagged images and
active rollback task revisions available; the ECR lifecycle policy deletes only
untagged images. Run HTTPS smoke checks after an operator-initiated rollback.

## EC2 application release

CodeDeploy drains traffic and installs one instance at a time. Deployment failure
or the configured ALB error alarm triggers automatic rollback. Post-release HTTPS
smoke failure causes the script to deploy the previous successful revision if one
exists. Every artifact is stored using S3 versioning; rollback retrieves the exact
revision referenced by CodeDeploy, rather than a mutable latest ZIP.

The release manifest records `previousDeploymentId`. The same rollback script
redeploys that revision and waits for success. The first release has no previous
successful deployment; fix the failed bootstrap/release and redeploy. Instance-local
release directories are retained for investigation; implement disk-retention
cleanup before adopting this sample for a long-running production fleet.

## Infrastructure and database

Review CloudFormation replacement/deletion changes before applying. Stack failure
uses CloudFormation rollback. For a completed unwanted change, revert the template
in Git and generate a new reviewed change set. Restoring a template does not restore
lost database contents, and a rollback may itself fail if external dependencies
have changed. Investigate stack events and resolve rollback failures explicitly.

RDS has 14-day backups and deletion protection in prod, with snapshot deletion
policy. Point-in-time restore creates a new DB instance; validate it, update the
endpoint through IaC and test before switching traffic. Credentials and network
rules also need validation. Multi-AZ is not regional disaster recovery; cross-region
backups and recovery objectives must be agreed and restore-tested separately.

The sample performs no schema migration. Future schema changes must use
expand/contract migrations and a dedicated migration role. Do not couple destructive
schema reversal to an automatic application rollback.
