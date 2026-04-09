# EKS Platform GitOps — Production-Grade AWS Kubernetes Platform

> A fully deployed, end-to-end cloud-native platform built on AWS EKS using Terraform, Argo CD GitOps, Karpenter, KEDA, and Prometheus/Grafana observability.

---

## 📌 About This Project

This is a **production-style platform** I designed and deployed end-to-end on AWS — not a tutorial or learning exercise.

The platform was fully running on AWS with real infrastructure, real GitOps deployments, and real observability. It has been taken offline to avoid ongoing AWS costs (~$10/day for the full stack), but **all infrastructure and deployment code is here and fully deployable.**

**CI/CD pipelines** were built in GitLab (`.gitlab-ci.yml`) and are included in this repository for reference.

---

## 🏗️ Architecture Overview

```
Users
  │
  ▼
AWS ALB (Application Load Balancer)
  │   [AWS Load Balancer Controller on EKS]
  ▼
EKS Cluster
  ├── CRUD Node Pool        (Karpenter — compute-optimized, on-demand)
  │     └── App Pods        (HPA on RPS + latency)
  │           └── PgBouncer (connection pooling → RDS)
  │
  └── AI/Bursty Node Pool   (Karpenter — spot instances, burst-friendly)
        └── App Pods        (KEDA — event-driven on queue depth)
              └── Vector DB + Inference workloads
  │
  ▼
Amazon RDS PostgreSQL (private subnet, Multi-AZ)
  │
  ▼
AWS Secrets Manager → External Secrets Operator → Kubernetes Secrets
```

**Key Design Decisions:**
- Separate Karpenter node pools for different workload types — prevents resource starvation
- KEDA for event-driven scaling (queue depth, active connections) instead of CPU-only HPA
- PgBouncer in transaction mode — protects RDS from connection storms
- IRSA + External Secrets — zero hardcoded credentials anywhere

---

## 📁 Repository Structure

```
.
├── infra-repo/          # Terraform — AWS infrastructure provisioning
├── platform-repo/       # GitOps — Argo CD Applications + Helm charts
└── app-repo1/           # Application — source code + Docker build
```

---

## 🔧 What's Inside Each Folder

### 1. `infra-repo/` — Infrastructure (Terraform)

Provisions the full AWS infrastructure from scratch:

| Resource | Details |
|---|---|
| VPC | Multi-AZ, public + private subnets |
| EKS Cluster | Managed node groups + Karpenter node pools |
| Karpenter | Separate NodePools for CRUD and bursty workloads |
| RDS PostgreSQL | Private subnet, Multi-AZ, encrypted |
| IAM + OIDC | IRSA-ready, least-privilege roles per service account |
| Remote State | S3 backend + DynamoDB locking |
| CI Pipeline | GitLab CI — fmt / validate / plan / apply |

**Terraform Workflow:**
```bash
cd infra-repo
terraform init
terraform fmt -recursive
terraform validate
terraform plan
terraform apply
```

---

### 2. `platform-repo/` — GitOps (Argo CD + Helm)

Deploys and manages all workloads on EKS using GitOps:

| Component | Details |
|---|---|
| Argo CD | Root app orchestration, sync waves for deploy order |
| Helm Charts | App deployment, service, ingress, ConfigMaps |
| KEDA ScaledObjects | Event-driven autoscaling on Prometheus metrics |
| External Secrets | DB credentials injected from AWS Secrets Manager |
| Argo CD Image Updater | Automatic image tag updates on new builds |
| Karpenter NodePools | Workload-aware node provisioning configs |

**Key Paths:**
```
platform-repo/
├── apps/
│   └── todo-app/          # Helm chart — Deployment, Service, Ingress
├── clusters/
│   └── prod/              # Argo CD Application manifests
└── keda/
    └── scaled-objects/    # KEDA ScaledObject configs per service
```

**Deploy/Sync:**

Once Argo CD is installed and pointing to this repo:
```bash
kubectl apply -f platform-repo/clusters/prod/root-app.yaml
```
Argo CD will reconcile and create all namespaces, deployments, services, ingress, and secrets automatically.

---

### 3. `app-repo1/` — Application (Python + Docker)

A Streamlit-based web application with PostgreSQL integration.

| Feature | Details |
|---|---|
| UI | Streamlit — login, todo management |
| Database | PostgreSQL (via PgBouncer connection pool) |
| Security | bcrypt password hashing |
| Observability | Prometheus metrics endpoint (`/metrics`) |
| Packaging | Docker — ECR-ready |

**Local Run (requires PostgreSQL):**
```bash
cd app-repo1/web_app_todo
pip install -r requirements.txt

export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=todo
export DB_USER=postgres
export DB_PASSWORD=postgres

streamlit run web.py --server.port 8501
```

**Docker Build:**
```bash
docker build -t eks-platform-app:local .
docker run -p 8501:8501 \
  -e DB_HOST=<host> \
  -e DB_PORT=5432 \
  -e DB_NAME=todo \
  -e DB_USER=<user> \
  -e DB_PASSWORD=<password> \
  eks-platform-app:local
```

---

## 🔑 Key Technologies & Why

| Technology | Why I Used It |
|---|---|
| **Karpenter** | Dynamic node provisioning based on actual pod resource requests — not fixed node groups. Separate pools for different workload types prevent resource starvation. |
| **KEDA** | Event-driven pod scaling on real signals (queue depth, active connections, Prometheus metrics) — not just CPU, which is misleading for DB-heavy and AI workloads. |
| **PgBouncer** | Transaction-mode connection pooling protects RDS from connection storms when many pods try to connect simultaneously. |
| **Argo CD** | GitOps-based deployments — Git is the single source of truth. All changes are auditable, reversible, and automatic. |
| **External Secrets Operator** | Syncs secrets from AWS Secrets Manager into Kubernetes — zero hardcoded credentials in code or manifests. |
| **IRSA** | IAM roles bound to Kubernetes service accounts via OIDC — no static AWS keys anywhere in the cluster. |
| **Prometheus + Grafana** | Golden signal dashboards (RPS, latency, error rate, saturation) per service — enables SLO-based alerting and capacity forecasting. |

---

## 🔒 Security Highlights

- RDS in **private subnets** — no public IP, no direct internet access
- **IRSA/OIDC** — Kubernetes service accounts get AWS permissions without static keys
- **External Secrets Operator** — credentials never stored in Git or container images
- **Least-privilege IAM** — separate roles per controller (ALB Controller, External Secrets, Image Updater, Karpenter)
- **Network policies** — pod-to-pod traffic restricted by namespace

---

## 📈 Observability

| Signal | Tool | What It Monitors |
|---|---|---|
| Metrics | Prometheus + Grafana | RPS, p95/p99 latency, error rate, pod count, node utilization |
| Logs | CloudWatch | Application logs, EKS control plane logs |
| Scaling events | Karpenter logs | Node provisioning and deprovisioning |
| DB performance | RDS Performance Insights | Query latency, connection count, wait events |

Grafana dashboards include:
- Golden signals per service
- Karpenter node scaling activity
- RDS connection pool utilization
- Cost tracking by node pool

---

## ✅ What I Built and Owned

This was a solo end-to-end build. I personally designed, implemented, and deployed:

- **Terraform modules** — VPC, EKS, RDS, IAM, Karpenter, remote state
- **GitOps structure** — Argo CD root app, Helm charts, sync waves, image updater
- **Karpenter NodePools** — workload-aware node provisioning with spot + on-demand mix
- **KEDA ScaledObjects** — event-driven autoscaling on Prometheus custom metrics
- **Observability stack** — Prometheus, Grafana, ServiceMonitor configs, alert rules
- **Security layer** — IRSA, External Secrets, least-privilege IAM, network policies
- **CI/CD pipelines** — GitLab CI for Terraform (fmt/validate/plan/apply) and Docker builds

---

## 🚀 Tech Stack

| Layer | Technologies |
|---|---|
| Cloud | AWS (EKS, RDS, VPC, IAM, Secrets Manager, ECR, S3) |
| Orchestration | Kubernetes, Helm, Karpenter, KEDA |
| GitOps | Argo CD, Argo CD Image Updater |
| IaC | Terraform |
| Observability | Prometheus, Grafana, CloudWatch |
| Security | IRSA, External Secrets Operator, AWS Secrets Manager |
| CI/CD | GitLab CI |
| Application | Python, Streamlit, Docker |
| Database | PostgreSQL (RDS), PgBouncer |

---

## 📝 Notes

- **Live URL:** Taken offline to control AWS costs. Full stack costs approximately $10/day when running.
- **CI/CD Pipelines:** Originally built in GitLab. `.gitlab-ci.yml` files are included in each sub-repo for reference.
- **Karpenter + KEDA configs:** See `infra-repo/` for NodePool definitions and `platform-repo/keda/` for ScaledObject configs.

---

## License

MIT



One Screenshot Helps
If you have a screenshot of:

The Argo CD dashboard showing the deployment
The Grafana dashboards
The Karpenter logs showing node scaling