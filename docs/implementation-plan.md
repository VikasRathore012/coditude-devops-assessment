# Assessment implementation plan

Goal: deliver reviewable source code today; no AWS deployment is required or claimed.

Architecture: alternative ECS Fargate and EC2 Auto Scaling deployment stacks,
with an HTTPS ALB, private compute, isolated RDS PostgreSQL, Secrets Manager,
CloudWatch, and separate infrastructure/application automation. Next.js serves
an intentionally small database-status UI; Python provides health and readiness
endpoints. No business schema or data migration is needed for this sample.

1. Create an API with liveness/readiness separation and tests for unavailable DB.
2. Build Next.js UI with runtime same-origin API requests and container files.
3. Generate CloudFormation foundation, ECS and EC2 templates and env examples.
4. Add GitHub Actions app/infra workflows and a native CodePipeline alternative.
5. Validate templates, shell, Python, frontend build, deployment contracts.
6. Document setup, limitations, secrets bootstrap, rollback, and architecture;
   package all source and local validation evidence into a ZIP.

Constraints: no credentials, no live resource creation, no Terraform substitution,
no fabricated deployment evidence. Keep app deployment permissions separate
from CloudFormation write permissions. A service DB login must be initialized
before readiness checks can pass; include the bootstrap script and directions.
