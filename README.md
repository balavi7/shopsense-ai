# ShopSense AI

An AI-powered customer support platform for ecommerce, built as a Forward Deployed Engineer (FDE) portfolio project.

Customers ask questions about their orders, refunds, and return policies — and get instant, accurate answers from a locally running LLM, grounded in a RAG knowledge base.

---

## What it does

- Answers customer queries about order status, refunds, and return policies
- Uses RAG (Retrieval Augmented Generation) to ground answers in real data, no hallucinations
- Logs every query and flags low-confidence answers for knowledge base improvement
- Fully containerized and deployed to AWS with automated CI/CD

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | FastAPI |
| LLM | Ollama (qwen2.5-coder:1.5b — runs locally) |
| Vector store | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Logging | SQLite |
| Containers | Docker + Docker Compose |
| Infra | Terraform (AWS EC2, S3, IAM, Security Group) |
| CI/CD | GitHub Actions |
| Cloud region | ap-south-1 (Mumbai) |

---

## Project structure

```
shopsense-ai/
├── backend/
│   ├── main.py              
│   ├── rag.py               
│   ├── ollama_client.py     
│   ├── logger.py            
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app.py               
│   ├── requirements.txt
│   └── Dockerfile
├── knowledge_base/
│   ├── order_policies.md   
│   ├── refund_rules.md      
│   └── mock_orders.json     
├── infra/
│   ├── main.tf              
│   ├── variables.tf
│   └── outputs.tf
├── .github/
│   └── workflows/
│       └── deploy.yml       
└── docker-compose.yml
```

---

## Local setup

**Prerequisites:** Docker, Docker Compose, Ollama installed and running

**1. Clone the repo**
```bash
git clone https://github.com/username/shopsense-ai.git
cd shopsense-ai
```

**2. Start all services**
```bash
docker compose up --build
```

**3. Open the app**
- Streamlit UI → http://localhost:8501
- FastAPI docs → http://localhost:8000/docs

---

## AWS deployment

**Prerequisites:** Terraform installed, AWS CLI configured, EC2 key pair created

**1. Provision infrastructure**
```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Fill in your key_pair_name and AWS details
terraform init
terraform apply
```

**2. Add GitHub Secrets**

Go to your repo → Settings → Secrets and variables → Actions:

| Secret | Value |
|---|---|
| `EC2_HOST` | Elastic IP from Terraform output |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | Contents of your `.pem` file |

**3. Push to main**
```bash
git push origin main
```

GitHub Actions automatically SSHes into EC2, copies the code, builds containers, and starts the app. Every push to `main` triggers a fresh deploy.

---

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | API and Ollama status |
| POST | `/chat` | Send a query, get an AI answer |
| GET | `/orders/{id}` | Look up an order by ID |
| POST | `/ingest` | Re-ingest knowledge base |
| GET | `/logs/stats` | Confidence rate, query count |
| GET | `/logs/unanswered` | Queries the AI couldn't answer confidently |

---

## The FDE loop

This project is structured around the Forward Deployed Engineer workflow:

- **Scoping** — Defined the customer problem and knowledge base structure
- **Prototyping** — Built RAG pipeline locally with ChromaDB and Ollama
- **Deployment** — Containerized with Docker, deployed to AWS via Terraform and GitHub Actions
- **Feedback** — Query logger surfaces knowledge gaps via `/logs/unanswered` for continuous improvement