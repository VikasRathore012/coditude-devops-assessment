# Deployment runbook (for an authorized AWS environment)

Deployment is not required for this submission and was not executed. The commands
below describe how the checked-in files are intended to be used. They create paid
resources if run with an authorized account. Use a non-production account first.

## 1. Prerequisites

AWS CLI v2, Python 3.12, Node.js 22, Git, Docker for Linux/amd64 images, a GitHub
repository, and AWS credentials via SSO/profile. Select a region with at least two
AZs and the required service availability. Validate RDS PostgreSQL 17.11 availability
and instance types before creating stacks. `DbEngineVersion` is configurable;
`DBParameters` is specifically the postgres17 family.

An administrator provides an account-governed CloudFormation execution role with
permission to manage this solution's VPC/routing/SGs, RDS, ECS/ECR, EC2 Auto Scaling,
ALB, S3, Secrets Manager, CloudWatch/Logs/SNS, CodeBuild/CodePipeline/CodeDeploy and
its IAM roles. It must trust `cloudformation.amazonaws.com`. This privileged role
is deliberately not created by the application pipeline. Restrict it with the
organization's permissions boundary/SCP, project naming and tagging controls.

Use a DNS hostname you control and an issued ACM certificate in the ALB's region.
The sample does not assume ownership of an existing hosted zone. Create an alias
record or CNAME to the runtime ALB output after provisioning; the hostname must
match the certificate before the release smoke check will succeed.

Bash examples below use:

```bash
export AWS_PROFILE=assessment
export AWS_DEFAULT_REGION=ap-south-1
export ENVIRONMENT=dev
export FOUNDATION_STACK=coditude-dev-foundation
export CFN_EXECUTION_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT:role/YOUR_APPROVED_CFN_ROLE
```

## 2. Foundation

Edit `infra/environments/dev.json` (or the chosen environment). The defaults are
separate CIDRs, small dev capacity, larger production DB class and no email.
Provide an operational alert email if desired and confirm its SNS subscription.

```bash
python scripts/infra_change_set.py --environment "$ENVIRONMENT" \
  --component foundation --execution-role "$CFN_EXECUTION_ROLE_ARN"
```

Review the changes printed by the script. For an approved plan:

```bash
export EXPECTED_STACK="$FOUNDATION_STACK"
export CHANGE_SET_ARN='PASTE_THE_EXACT_REVIEWED_ARN'
python scripts/apply_change_set.py
```

The same plan/apply scripts manage runtime stacks. They do not auto-approve
resource replacement. A no-change CloudFormation plan reports its AWS reason and
exits non-zero; it is not a deployment failure and should not be applied.

## 3. Initialize the dedicated database login

Secrets Manager generates an application credential but cannot itself create a
PostgreSQL role. The separate bootstrap stack solves that dependency. It runs
CodeBuild inside the private subnets with access to the RDS-admin and app secrets;
the normal application roles never receive the admin secret.

```bash
ARTIFACT_BUCKET=$(aws cloudformation describe-stacks --stack-name "$FOUNDATION_STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='Artifacts'].OutputValue" --output text)
python -m zipfile -c /tmp/assessment-db-bootstrap.zip scripts/bootstrap_db.py
# zipfile -c stores basename bootstrap_db.py, which the buildspec expects.
aws s3 cp /tmp/assessment-db-bootstrap.zip "s3://$ARTIFACT_BUCKET/bootstrap/source.zip"
aws cloudformation deploy --stack-name "coditude-$ENVIRONMENT-db-bootstrap" \
  --template-file infra/database-bootstrap.yaml --capabilities CAPABILITY_IAM \
  --role-arn "$CFN_EXECUTION_ROLE_ARN" --parameter-overrides FoundationStack="$FOUNDATION_STACK"
BOOTSTRAP_PROJECT=$(aws cloudformation describe-stacks --stack-name "coditude-$ENVIRONMENT-db-bootstrap" \
  --query "Stacks[0].Outputs[?OutputKey=='Project'].OutputValue" --output text)
aws codebuild start-build --project-name "$BOOTSTRAP_PROJECT"
```

Wait for that build to report `SUCCEEDED` in CodeBuild; use `batch-get-builds`
with its returned build ID. If it fails, inspect the build log before continuing.
Then delete the bootstrap stack to remove the temporary privileged build role.
The script is idempotent and serialized with a PostgreSQL advisory lock. It grants
only CONNECT; the demo only runs `SELECT 1`. For future business tables, introduce
versioned migrations and explicit schema/table grants in a separate migration job.

## 4A. Containerized runtime

Publish initial image digests before creating ECS services:

```bash
REVISION=$(git rev-parse HEAD)
python scripts/deploy_app.py --foundation "$FOUNDATION_STACK" \
  --mode ecs --revision "$REVISION" --build-only
```

Copy the two `images` values from `dist/release.json` into `ecs.FrontendImage` and
`ecs.BackendImage` in the environment JSON. Set `CertificateArn` to your issued
certificate ARN. Create/review/apply the `ecs` change set using the same scripts:

```bash
python scripts/infra_change_set.py --environment "$ENVIRONMENT" \
  --component ecs --execution-role "$CFN_EXECUTION_ROLE_ARN"
# Then apply its exact reviewed ARN with EXPECTED_STACK=coditude-dev-ecs.
```

Map your hostname to the ALB output. Check `/health` and `/api/ready`. A later
application release changes image revisions without changing the infrastructure:

```bash
python scripts/deploy_app.py --foundation "$FOUNDATION_STACK" \
  --runtime "coditude-$ENVIRONMENT-ecs" --mode ecs \
  --revision "$(git rev-parse HEAD)" --url https://YOUR_APPLICATION_HOSTNAME
```

## 4B. Non-containerized runtime

Set `ec2.CertificateArn` in the environment JSON. Plan/apply `component=ec2`.
CloudFormation creates two private Amazon Linux 2023 instances. User data installs
Node.js 22, Python 3.12, CodeDeploy and CloudWatch agents. Verify user-data and agent
startup before the first release. The 900-second ASG health grace allows initial
bootstrap; submit the initial CodeDeploy release promptly rather than leaving
empty instances unhealthy indefinitely.

```bash
python scripts/deploy_app.py --foundation "$FOUNDATION_STACK" \
  --runtime "coditude-$ENVIRONMENT-ec2" --mode ec2 \
  --revision "$(git rev-parse HEAD)" --url https://YOUR_EC2_APPLICATION_HOSTNAME
```

The release packages the Next.js standalone server, static assets, Python source,
pinned Python requirements, RDS trust certificate, AppSpec and hooks. CodeDeploy
drains target traffic and updates one instance at a time. It installs a release
virtualenv, updates systemd and checks both local frontend and DB readiness.
New ASG instances receive the last successful CodeDeploy revision via the
CodeDeploy/ASG integration. The first release has no prior successful revision.

This is a practical assessment bootstrap, not a claim of hardened golden-image
supply-chain validation. For production, bake and test these runtimes/agents into
an AMI, pin that AMI ID, and use reviewed image replacements for OS patching.
The provided SSM AMI parameter resolves the region's current AL2023 image.

## 5. Configure GitHub Actions

Create the repository and push all files, including `.github/workflows`.
Create GitHub environments `dev`, `staging`, `prod`, `infra-dev`, `infra-staging`
and `infra-prod`. Restrict their deployment branches; require reviewers for
production and infrastructure apply operations. Merely naming an environment in
YAML does not configure these protections.

Create the account-level GitHub OIDC provider from `infra/github-oidc.yaml` only
if one is not already present. Reuse the existing ARN otherwise.

Deploy `infra/infra-access.yaml` with the repository, exact `infra-ENV` environment
subject, OIDC provider, existing execution role ARN and environment stack prefix.
Deploy `infra/app-delivery.yaml` separately for the selected runtime. Required inputs:

| Parameter | Value |
|---|---|
| FoundationStack / RuntimeStack | Actual foundation and selected runtime stack names |
| Mode | `ecs` or `ec2` |
| GitHubRepository | `OWNER/REPOSITORY` |
| GitHubEnvironment | `dev`, `staging` or `prod` |
| GitHubOidcProviderArn | Existing account-level provider ARN |
| AppUrl | HTTPS application hostname pointing to the runtime ALB |
| Driver | `github` for this path |
| EcsServiceArns | ECS only: exact frontend and backend service ARNs, comma-separated |
| EcsTaskRoleArns | ECS only: exact frontend task role, backend task role, execution role ARNs |
| CodeDeployApplicationName / CodeDeployGroupName | EC2 only: actual runtime outputs |

Find ECS service ARNs with `aws ecs describe-services` using the runtime `Cluster`,
`FrontendService` and `BackendService` outputs. Role ARNs are direct runtime outputs.
Do not leave ECS ARN placeholders when Mode=ecs; they intentionally grant no access.

Set repository variable `DEPLOY_DRIVER=github` only when cloud releases are wanted.
In each application environment set `AWS_APP_ROLE_ARN`, `AWS_REGION`,
`FOUNDATION_STACK`, `RUNTIME_STACK`, `DEPLOY_MODE` and `APP_URL`.
In each infrastructure environment set `AWS_INFRA_ROLE_ARN`, `AWS_REGION` and
`CFN_EXECUTION_ROLE_ARN`. No AWS access-key secrets are needed.

Branch mapping: main -> dev; staging -> staging; production -> prod. App-only path
changes run app tests/build/release. Infra-only changes run validation; manually
run infrastructure `plan`, review the change set, then run `apply` with its ARN.
Protect application and deployment-script changes with PR review/CODEOWNERS.

## 6. AWS-native application delivery alternative

Create and authorize a GitHub CodeConnections connection. Its status must be
AVAILABLE; CloudFormation cannot complete the external GitHub authorization.
Deploy the same `app-delivery.yaml` with `Driver=native`, the real `ConnectionArn`,
and the environment branch. Keep `DEPLOY_DRIVER` unset or set it to `native` in
GitHub to disable GitHub cloud releases. Never enable both release drivers for
the same target.

CodePipeline V2 filters application paths, retrieves source through the
connection and passes it to CodeBuild. A manual approval stage exists for prod.
CodeBuild tests, builds and invokes the same application-only deployment script;
ECS uses service revision updates and EC2 uses CodeDeploy. The build role has an
explicit CloudFormation write deny. Infrastructure remains in its separate
reviewed GitHub change-set workflow regardless of the selected app driver.

## 7. Production verification before enabling traffic

Confirm ALB targets and HTTPS certificate/DNS, both application endpoints,
private database connectivity, Secrets Manager access, two-AZ capacity, alarm
notifications, backup restore and actual rollback behavior. Inspect container
scan findings; scan the native dependency bundle too. Perform load and AZ-failure
exercises. These checks require AWS and are not included in the offline evidence.

## 8. Cleanup

Disable pipeline triggers first. Delete delivery/runtime stacks before the
foundation because of exported-value dependencies. Production ALB/RDS deletion
protection must be intentionally disabled through a reviewed infrastructure
change before deletion. Database deletion produces a snapshot. Artifact buckets,
ECR repositories, app secrets and selected log groups are retained and continue
to incur storage charges until an authorized operator removes them. Do not
blindly force-delete retained data.
