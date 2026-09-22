# Coditude DevOps assessment

**Submission: Vikas Singh Rathore**

This repository demonstrates the implementation approach for Next.js, Python and
PostgreSQL on AWS. It includes CloudFormation, both deployment models, application
source, GitHub Actions, AWS-native application delivery, and operational runbooks.

**Assessment boundary:** the hiring team confirmed that an AWS deployment is not
required. No AWS resources were created, and this repository does not claim a
successful cloud deployment. See [validation evidence](docs/validation.md) for what
was actually checked. Account-specific inputs are deliberately marked
`REPLACE_WITH_...`; they are configuration values, not missing application logic.

## Start reviewing here

1. [Architecture and decisions](docs/architecture.md) and [PNG diagram](docs/architecture.png).
2. `infra/foundation.yaml`: VPC, subnets, routing, PostgreSQL, secrets, ECR, artifacts and alarms.
3. `infra/ecs.yaml` and `infra/ec2.yaml`: alternative runtime implementations.
4. `.github/workflows/`: separate application and infrastructure workflows.
5. `infra/app-delivery.yaml` and `ci/buildspec-app.yml`: AWS-native delivery alternative.
6. [Deployment runbook](docs/deployment.md), [security](docs/security.md), and [rollback](docs/rollback.md).

## Requirements coverage

| Requirement | Implementation |
|---|---|
| Next.js frontend, Python backend, PostgreSQL | `apps/`, `compose.yaml`, RDS in foundation template |
| Containerized deployment | Two independent ECS Fargate services, private networking, ECR digest releases |
| Non-containerized deployment | Private EC2 Auto Scaling fleet, systemd processes, CodeDeploy artifacts |
| CloudFormation | Seven YAML templates, explicit inputs/outputs and environment files |
| Dev / Staging / Production | Separate named stacks and CIDRs; production Multi-AZ RDS and two NAT gateways |
| GitHub Actions | Application tests/build/release; infrastructure validation and reviewed change sets |
| AWS-native CI/CD | CodePipeline V2 source/path filtering, approval for production, CodeBuild build/test/deploy; CodeDeploy for EC2 |
| Application/infra separation | Separate triggers and roles; explicit CloudFormation write deny on application identities |
| Secrets | Dedicated DB login, Secrets Manager runtime retrieval, separate privileged bootstrap |
| High availability and scale | Two-AZ compute, two minimum replicas/instances, CPU target tracking, Multi-AZ DB in production |
| Monitoring | CloudWatch logs, Container Insights, ALB unhealthy/5xx alarms, RDS disk alarm, VPC reject flow logs, SNS |
| Rollback | ECS circuit breaker plus two-service rollback; CodeDeploy rollback and explicit rollback script |
| Documentation and diagram | This README and `docs/` |

## Offline review: no AWS account needed

Linux, macOS, or Windows WSL2/Git Bash is recommended for these commands.
Use Python 3.12, Node.js 22, and npm. No AWS authentication is needed for these checks.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r apps/backend/requirements.txt -r requirements-dev.txt
python -m pytest tests -q
cfn-lint -t infra/*.yaml
python scripts/validate_repository.py
cd apps/frontend
npm ci
npm run build
cd ../..
python scripts/smoke_frontend.py
```

Windows PowerShell virtual environment activation: `.venv\Scripts\Activate.ps1`.
Run shell syntax checks through WSL2/Git Bash.

Optional local end-to-end demo, if Docker is installed:

```bash
cp .env.example .env
docker compose up --build
# Open http://localhost:8080 and click Check API and database.
# Stop while retaining data:
docker compose down
```

The local password is a development-only value. PostgreSQL is not published to
any host port. The local gateway binds to loopback only. AWS uses HTTPS and verified
RDS TLS; local Compose uses HTTP on loopback and a private Docker network.

## Repository layout

- `apps/frontend/`: Next.js UI and health endpoint; lockfile and Dockerfile.
- `apps/backend/`: FastAPI health/readiness API; pinned requirements and Dockerfile.
- `infra/`: foundation, ECS, EC2, DB bootstrap, GitHub OIDC, infrastructure access, and app delivery.
- `infra/environments/`: dev/staging/prod settings.
- `deploy/ec2/`: CodeDeploy AppSpec, lifecycle hooks and systemd units.
- `scripts/`: application releases, rollbacks, change-set planning/apply, bootstrap and validation.
- `ci/`: AWS CodeBuild build specification.
- `.github/workflows/`: GitHub Actions pipelines (include this hidden folder when uploading).
- `docs/`: architecture, deployment, security, rollback, limitations and validation evidence.

## Submit today

Create a GitHub repository, extract this ZIP and push the repository contents:

```bash
git init
git add .
git commit -m "Add Coditude DevOps assessment implementation"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/coditude-devops-assessment.git
git push -u origin main
```

Share the repository URL. If private, grant the reviewers access. You can also
attach this ZIP. No cloud setup is necessary for submission. Keep the
`DEPLOY_DRIVER` repository variable unset: tests can run but cloud release stays disabled.
