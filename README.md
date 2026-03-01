# ✅ Todo App Platform (AWS EKS + GitOps + RDS PostgreSQL)

A production-style **Todo Web Application** deployed on **AWS EKS** using **Terraform (IaC)** + **Argo CD GitOps**, backed by **Amazon RDS PostgreSQL**, with **observability-ready metrics** and secure secret management.

> This repo is organized as a 3-part platform:
> - **infra-repo** → Terraform provisions AWS infrastructure (VPC, EKS, RDS, IAM, etc.)
> - **platform-repo** → GitOps deployment (Argo CD Applications + Helm charts)
> - **app-repo1** → Application source code + Docker build

---

## 🌐 Live Application Access

### ✅ Live URL (what to paste in the application form)
**Live App URL:** `http://<ALB_DNS_NAME>/`

You can retrieve the ALB DNS using:

```bash
kubectl get ingress -n todo-app


Look under the ADDRESS column and open it in the browser.

Example:

todo-app   alb   <ALB_DNS_NAME>   ...

If your Ingress is configured with a host, then use:
http://<host>/
Otherwise ALB DNS works directly.

🔐 Test Credentials (if login is enabled)

If your live app requires authentication, provide either:

a test username/password, OR

clear steps to self-create a user inside the app.

Option A — Provide test credentials

Username/Email: <your-test-user>

Password: <your-test-password>

Option B — Self-create

Open the Live URL

Click Sign Up

Create a user (no manual approval required)

⚠️ Applications without access credentials typically won’t be reviewed.

🧩 Architecture Overview
High-level Flow

Users access the app through an AWS Application Load Balancer (ALB) created via the AWS Load Balancer Controller on EKS.

The application runs as a containerized Streamlit service and connects privately to Amazon RDS PostgreSQL.

Secrets are injected securely using External Secrets Operator + AWS Secrets Manager, and Kubernetes access is secured via IRSA (OIDC).

Diagram (Mermaid)
🔒 Security Highlights

RDS in private subnets (no public IP)

IRSA/OIDC for Kubernetes service accounts (no static AWS keys)

Secrets from AWS Secrets Manager synced into Kubernetes via External Secrets

Least-privilege IAM for controllers (ALB Controller, External Secrets, Image Updater, etc.)

📈 Observability

The application exposes metrics (Prometheus format), making it easy to integrate with:

Prometheus scraping

Grafana dashboards

Alerting rules (future-ready)

📁 Repository Structure (All Three Folders)
.
├── app-repo1/           # Application source + Docker build
├── infra-repo/          # Terraform infrastructure provisioning
└── platform-repo/       # GitOps deployment (Argo CD + Helm)
1) 🚀 app-repo1 — Application (Streamlit + Docker)

Path: app-repo1/web_app_todo/

What it contains

Streamlit-based Todo UI

PostgreSQL integration (users + todos)

Password hashing (bcrypt)

Metrics endpoint (Prometheus client)

Dockerfile for container build

Local Run (optional)

If you want to run locally (requires PostgreSQL):

cd app-repo1/web_app_todo
pip install -r requirements.txt

export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=todo
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_SSLMODE=disable

streamlit run web.py --server.port 8501

Open:

http://localhost:8501

Docker Build (optional)
cd app-repo1/web_app_todo
docker build -t todo-app:local .
docker run -p 8501:8501 \
  -e DB_HOST=<dbhost> -e DB_PORT=5432 -e DB_NAME=todo \
  -e DB_USER=<user> -e DB_PASSWORD=<pass> \
  todo-app:local
2) 🏗️ infra-repo — Infrastructure (Terraform)

Goal: Provision AWS infrastructure for a production-style Kubernetes deployment.

What it provisions

Multi-AZ VPC with public & private subnets

EKS cluster

RDS PostgreSQL (private)

IAM roles + OIDC provider (IRSA-ready)

Terraform remote state (S3 + DynamoDB locking)

CI pipeline for fmt/validate/plan/apply

Typical Terraform Workflow
cd infra-repo
terraform init
terraform fmt -recursive
terraform validate
terraform plan
terraform apply

Outputs include RDS endpoint and secret ARN (depending on modules/outputs).

3) ⚙️ platform-repo — GitOps (Argo CD + Helm)

Goal: Deploy everything on EKS using GitOps, including the todo-app, controllers, and secrets.

What it contains

Argo CD Applications (root app orchestration)

Helm chart for todo-app

External Secret definitions for DB creds

Deploy order controlled using sync waves

Image automation support (Argo CD Image Updater)

Key Paths

platform-repo/apps/todo-app/
Helm chart + templates (Deployment, Service, Ingress, ConfigMaps)

platform-repo/clusters/prod/
Production overlays / Argo CD Application manifests

Deploy/Sync

Once Argo CD is installed and pointing to this repo, Argo CD sync will create:

Namespace todo-app

Todo deployment + service + ingress

ExternalSecrets that inject DB credentials into the pods

✅ What I Personally Built / Owned

End-to-end cloud-native platform implementation:

Terraform-based AWS provisioning (VPC/EKS/RDS/IAM)

GitOps deployment (Argo CD Applications + Helm)

Containerized application packaging (Docker/ECR-ready)

Secure secrets flow (AWS Secrets Manager → External Secrets → Kubernetes)

ALB Ingress routing to live app on EKS

🧭 Troubleshooting (Quick)
Get the live app ALB address
kubectl get ingress -n todo-app
Check pod health
kubectl get pods -n todo-app
kubectl describe pod <pod> -n todo-app
kubectl logs <pod> -n todo-app
Check DB connectivity from cluster
kubectl -n todo-app get secret todo-app-db-secret -o yaml
📌 Tech Stack

AWS: EKS, RDS PostgreSQL, VPC, IAM, Secrets Manager

Kubernetes: Ingress, Services, Deployments, ConfigMaps, Secrets

GitOps: Argo CD (+ Image Updater support)

IaC: Terraform

App: Python + Streamlit

Observability: Prometheus metrics endpoint (Grafana-ready)

License

MIT (or your preferred license)


---

If you tell me your **actual Live ALB DNS** (or paste `kubectl get ingress -n todo-app` outpu