# Infra Repo — AWS EKS + RDS (Todo App Platform)

This repository provisions the AWS infrastructure used to run the **Todo application** on Kubernetes (EKS).  
It follows a production-style setup with:
- Remote Terraform state in **S3** with locking in **DynamoDB**
- Multi-AZ **VPC** with public + private subnets
- **EKS cluster** with node groups (and Karpenter support)
- **RDS PostgreSQL** in private subnets
- IAM best practices including **OIDC + IRSA** for Kubernetes service accounts
- GitLab CI pipeline for `fmt/validate/plan/apply`

---

## High-level Architecture

- **VPC**
  - 2 AZs
  - Public subnets: Internet Gateway, NAT Gateway, (ALB targets)
  - Private subnets: EKS nodes/pods, internal services, RDS access
  - Added **VPC endpoints** (S3, ECR, STS, CloudWatch) to reduce NAT traffic and restrict egress
  - Subnet tags for Load Balancer Controller:
    - `kubernetes.io/role/elb=1` (public)
    - `kubernetes.io/role/internal-elb=1` (private)
    - `kubernetes.io/cluster/<cluster>=shared`


- **EKS**
  - Control plane managed by AWS
  - Worker nodes in **private subnets**
  - Cluster authentication via AWS CLI token (`aws eks get-token`)

- **RDS PostgreSQL**
  - Deployed into **private subnets** (no public access)
  - Security Groups restrict DB access to EKS node / cluster security groups only
  - Added **multi-AZ RDS** by default for failover 


- **IRSA (OIDC)**
  - Enables least-privilege IAM roles for Kubernetes service accounts
  - Reduces need for node IAM over-permissions

- **CI/CD**
  - GitLab pipeline runs `terraform fmt` + `terraform validate`
  - Plan/apply can be configured to run on MR/main depending on rules

> **Note:** Application workloads (Todo app Helm/ArgoCD manifests) are typically in a separate “platform/app repo”.
This repo focuses on foundational cloud infrastructure.
## Secrets Flow (GitLab → Secrets Manager → External Secrets)

- GitLab token is provided as a **masked/protected CI variable**.
- Terraform stores it in **AWS Secrets Manager** (not committed in tfvars).
- Platform repo uses **External Secrets** to sync the secret into the cluster for ArgoCD Image Updater.


---

## Repository Layout

infra-repo/
│
├── main.tf                # Root module entry (calls all modules)
├── variables.tf           # Global variables
├── outputs.tf             # Root outputs
├── providers.tf           
├── versions.tf             
│
├── modules/               # Reusable Terraform modules
│   │
│   ├── network/           # VPC, subnets, NAT, route tables, VPC endpoints
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── vpc.tf
│   │   ├── subnets.tf
│   │   ├── nat.tf
│   │   └── endpoints.tf
│   │
│   ├── eks-cluster/       # EKS control plane
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   ├── node-groups/       # Worker nodes (private subnets)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   ├── eks-addons/        # Core add-ons (vpc-cni, coredns, kube-proxy, ALB)
│   │
│   ├── oidc-provider/     # OIDC provider for IRSA (EKS service accounts)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   ├── irsa-roles/        # IAM roles for Kubernetes service accounts
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   ├── karpenter/         # Cluster autoscaling (optional but prod-grade)
│   │
│   ├── rds-postgres/      # PostgreSQL RDS module (private subnets)
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
│   
│
└── envs/
    ├── dev/               # Dev environment
    │   ├── terraform.tfvars
    │   └── backend.hcl
    │
    └── prod/              # Production environment
        ├── terraform.tfvars   # Environment variables
        └── backend.hcl        # Remote state backend config




---

## Prerequisites

- Terraform >= 1.5
- AWS CLI authenticated to the target AWS account
- An S3 bucket for Terraform state
- A DynamoDB table for state locking

Example backend resources:
- S3 bucket: `kishnazbucket`
- DynamoDB table: `terraform-locks` with partition key `LockID` (String)

---

## Remote State (S3 backend)

This repo uses environment-specific backend config files.

`envs/prod/backend.hcl` example:
```hcl
bucket         = "kishnazbucket"
key            = "prod/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-locks"
encrypt        = true
```



## How to Deploy (Local)

> This repo provisions AWS infrastructure only. Application deployment (Helm/ArgoCD manifests) typically lives in a separate repo.

```bash

1) Configure AWS Credentials
Ensure your AWS CLI is authenticated to the correct account:

aws sts get-caller-identity

2) Initialize Terraform Backend (Prod)
terraform fmt -recursive
terraform init -reconfigure -backend-config=envs/prod/backend.hcl

3) Validate + Plan
terraform validate
terraform plan -var-file=envs/prod/terraform.tfvars

4) Apply
terraform apply -var-file=envs/prod/terraform.tfvars

5) Configure kubectl for the EKS Cluster
After apply completes:
aws eks update-kubeconfig --region us-east-1 --name <cluster_name>
kubectl get nodes

6) Verify RDS Connectivity (from inside cluster)

RDS is not public. Access should be tested from inside the VPC (e.g., an EKS pod).

Example (temporary pod):

kubectl -n default run pg-client --image=postgres:16-alpine --restart=Never -it --rm -- sh
psql "host=<rds_endpoint> port=5432 dbname=<db> user=<user> sslmode=require"

```



## Architecture Diagram (Infra Repo)


                ┌────────────────────────────┐
                │        Internet Users       │
                └────────────┬───────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │   Public ALB   │
                    │ (Ingress/HTTPS)│
                    └────────┬───────┘
                             │
                ┌────────────┴────────────┐
                │         AWS VPC         │
                │       (Multi-AZ)        │
                └────────────┬────────────┘

        ┌──────────────────────────────┐
        │        Public Subnets         │
        │  AZ-a              AZ-b       │
        │  IGW               IGW        │
        │  NAT Gateway (one NAT per AZ )│
        └────────────┬─────────────────┘
                     │
                     ▼

        ┌──────────────────────────────┐
        │     Private App Subnets       │
        │      (EKS Worker Nodes)       │
        │      Kubernetes Pods          │
        └────────────┬─────────────────┘
                     │ DB connection (5432)
                     ▼

        ┌──────────────────────────────┐
        │      Private DB Subnets       │
        │      RDS PostgreSQL           │
        │   (not publicly accessible)   │
        └──────────────────────────────┘


Traffic Flow:
Users → ALB → EKS → RDS
EKS → Internet → NAT Gateway → IGW


### Notes
- EKS worker nodes and pods run in **private subnets**; ingress is through an **internet-facing ALB**.
- RDS PostgreSQL is deployed using a **DB subnet group backed by private subnets** and is **not publicly accessible**.
- DB access follows **least privilege** using a dedicated DB security group that only allows inbound PostgreSQL from approved security groups (e.g., EKS nodes/cluster).
- The master password is generated and stored in **AWS Secrets Manager** (`manage_master_user_password=true`) and RDS logs are exported to **CloudWatch**.



---

### Design Decisions

```md
## Design Decisions

### Why Terraform (IaC)
- Terraform enables reproducible, version-controlled infrastructure and consistent deployments across environments.
- Remote state (S3) + locking (DynamoDB) enables safe collaboration and prevents state corruption.
- Modular structure allows reuse and clean separation of responsibilities (VPC, EKS, RDS, IRSA, add-ons).

### Why EKS (Kubernetes)
- Kubernetes provides portability and a standard platform for deploying microservices and internal tooling.
- EKS offers a managed control plane with native AWS integrations.
- Running worker nodes in private subnets improves security posture and aligns with production practices.
- If the goal is minimum ops for one service, I’d deploy this on ECS Fargate. In this take-home I used EKS to demonstrate a reusable platform foundation with GitOps and least-privilege pod IAM via IRSA.”

### Why RDS PostgreSQL (Private)
- The application requires a transactional relational datastore (users/todos) with ACID guarantees.
- PostgreSQL offers a mature SQL feature set (constraints/indexes/migrations) that fits common SaaS backends.
- Amazon RDS reduces operational overhead (backups, patching, monitoring) while keeping the database private and locked down via security groups.
- Scaling path is clear: vertical scale first, add read replicas for read-heavy traffic, and consider Aurora PostgreSQL for elastic scaling if needed.

### Why this VPC layout (Public/Private + Multi-AZ)
- Public subnets are used for internet-facing components (ALB, NAT).
- Private subnets are used for compute and database to prevent direct internet exposure.
- Multi-AZ subnet design improves availability and reduces AZ failure blast radius.
- Single NAT is cost-optimized but not AZ-resilient. For production HA, I deploy one NAT per AZ and route each private subnet to its local NAT.

### Why Secrets Manager for DB master password
- `manage_master_user_password=true` stores the generated DB secret in AWS Secrets Manager.
- Avoids putting credentials in Terraform variables, Git, or CI logs.
- Improves security and supports future rotation strategies.

### Why the Todo app uses Python (application layer)
- Python is fast to iterate and widely used for building APIs and internal tools.
- Strong ecosystem for web frameworks and instrumentation (Prometheus client libraries, structured logging).
- In platform context, the language is less important than containerization, deployability, observability, and reliability patterns.

## Cost vs High Availability Tradeoffs

- This infrastructure is designed to balance availability, security, and cost:
- Multi-AZ VPC (2 AZs): improves resilience to an AZ outage, with subnets spread across two Availability Zones.
- NAT Gateway per AZ: increases availability for private subnet egress (each AZ routes to its local NAT), but NAT gateways are a significant cost driver.
- Cost optimization option: for lower environments (dev), use a single NAT to reduce cost at the expense of AZ-level egress resilience.
- VPC Endpoints (S3/ECR/STS/CloudWatch Logs): reduce NAT traffic (and cost) by keeping AWS service access private and avoiding internet egress where possible.
- RDS PostgreSQL in private subnets: reduces attack surface.
- For HA, Multi-AZ RDS can be enabled in production for automatic failover; in dev/test, Single-AZ is more cost-efficient.
- EKS vs ECS: EKS provides platform flexibility and supports multiple services/add-ons, but has higher operational complexity than ECS for a single small app. The choice here prioritizes platform extensibility.

## Scalability Approach

Scaling is handled at multiple layers (application, cluster, and database):
1) Ingress / Load Balancing
The application is exposed via an ALB Ingress, which can scale with increased request volume.
Health checks and target group status provide early signals for backend saturation.
2) Kubernetes Workloads
Use Horizontal Pod Autoscaler (HPA) to scale pods based on CPU/memory (or custom metrics like request rate/latency).
Apply resource requests/limits to ensure predictable scheduling and avoid noisy-neighbor issues.
3) Cluster Capacity
Use Karpenter (or Cluster Autoscaler) to automatically add/remove nodes based on pending pods and scheduling demand.
Spread nodes across AZs and use topology spread constraints / PDBs for higher availability during scaling events.
4) Database Scaling
Start with vertical scaling (larger instance class) for quick capacity increases.
Add read replicas for read-heavy workloads and/or introduce caching (e.g., Redis/ElastiCache) for hot reads.
Add connection pooling (pgBouncer / RDS Proxy) to protect the DB from connection storms during traffic spikes.
5) Observability and Triggers
Key signals for scaling decisions: p95/p99 latency, error rate (4xx/5xx), CPU/memory saturation, DB connections, and DB read/write latency.


## Improvements / If I Had More Time

### Security Hardening
- Add **WAF** in front of ALB for common attack protection.
- Add Kubernetes policy controls (e.g., Pod Security Standards, admission policies) depending on cluster requirements.

### Observability
- Add standard dashboards/alerts (latency p95/p99, error rates, saturation).
- Enable/standardize log shipping for workloads (CloudWatch, OpenSearch, or centralized log pipeline).

## RDS Postgres
- Define backup retention (e.g., 7–14 days) and enable Point-in-Time Recovery.
- Add maintenance window and minor version auto-upgrades (or pin versions and manage upgrades deliberately).
- Consider cross-region snapshot copy (DR) for higher resilience.


### Debug guide 

If application is down:
Check in order:
- Check last deploy / last MR / last config change first.
- DNS
- ALB health
- Target group
- Nodes
- Pods
- App logs
- Database






