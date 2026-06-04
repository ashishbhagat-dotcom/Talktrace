# Talktrace Deployment Guide

## Prerequisites

- A Linux server (Ubuntu 22.04+ recommended) with at least **8GB RAM** and **50GB disk**
- SSH access as root
- Domain or IP address
- GitHub access (repo is public)

---

## 1. Connect to the Server

```bash
ssh root@<SERVER_IP>
```

---

## 2. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
```

Verify:
```bash
docker --version
docker compose version
```

---

## 3. Clone the Repository

```bash
git clone https://github.com/ashishbhagat-dotcom/Talktrace.git /root/Talktrace
cd /root/Talktrace
```

---

## 4. Configure Environment

```bash
cp .env.example .env
nano .env
```

Set the following values:

```env
# Django
SECRET_KEY=<generate a long random string>
DEBUG=False
ALLOWED_HOSTS=<SERVER_IP>,localhost,127.0.0.1,django,*

# Database (leave defaults unless you changed them)
POSTGRES_DB=conv_intel
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<strong password>
DATABASE_URL=postgres://postgres:<password>@postgres:5432/conv_intel

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=<strong password>
MINIO_BUCKET_NAME=conversations
USE_MINIO=True
SERVER_IP=<SERVER_IP>

# LLM — use ollama if server has GPU/high RAM, openai otherwise
LLM_PROVIDER=ollama
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b
WHISPER_MODEL=base

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200

# CORS
CORS_ALLOWED_ORIGINS=http://<SERVER_IP>

# JWT
JWT_ACCESS_TOKEN_LIFETIME=60
JWT_REFRESH_TOKEN_LIFETIME=7

# Zoho CRM
ZOHO_CLIENT_ID=<your_zoho_client_id>
ZOHO_CLIENT_SECRET=<your_zoho_client_secret>
ZOHO_ACCOUNTS_URL=https://accounts.zoho.com
ZOHO_API_URL=https://sandbox.zohoapis.com
ZOHO_REDIRECT_URI=http://<SERVER_IP>/api/integrations/zoho/callback/
FRONTEND_URL=http://<SERVER_IP>
```

> Generate a secret key with:
> ```bash
> python3 -c "import secrets; print(secrets.token_urlsafe(50))"
> ```

---

## 5. Build and Start Containers

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This builds all images and starts:
- **nginx** (frontend on port 80)
- **Django** (gunicorn)
- **Celery Worker + Beat**
- **PostgreSQL, Redis, Elasticsearch, MinIO**

> First build takes **10–20 minutes** — it downloads and installs PyTorch, Whisper, and all ML dependencies (~3GB image).

Monitor build progress:
```bash
docker compose -f docker-compose.prod.yml logs -f
```

---

## 6. Run Migrations & Collect Static Files

Wait for all containers to be healthy, then:

```bash
docker compose -f docker-compose.prod.yml exec django python manage.py migrate
docker compose -f docker-compose.prod.yml exec django python manage.py collectstatic --noinput
```

---

## 7. Create Admin User

```bash
docker compose -f docker-compose.prod.yml exec django python manage.py shell -c "
from django.contrib.auth import get_user_model
U = get_user_model()
U.objects.create_superuser(email='admin@talktrace.io', password='<password>', name='Admin', role='admin')
print('Admin created')
"
```

---

## 8. Verify Deployment

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

All containers should show `Up` and health checks should be `(healthy)`.

Open `http://<SERVER_IP>` in your browser.

---

## 9. Zoho CRM Setup

1. Go to [api-console.zoho.com](https://api-console.zoho.com)
2. Open your client → **Edit**
3. Add to **Authorized Redirect URIs**:
   ```
   http://<SERVER_IP>/api/integrations/zoho/callback/
   ```
4. Log in to Talktrace → **Settings** → **Connect Zoho CRM**

---

## Deploying Updates

After pushing changes to GitHub:

```bash
cd /root/Talktrace
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec django python manage.py migrate
```

> Subsequent builds are much faster (~2–3 min) because Docker caches image layers.

---

## Useful Commands

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f django
docker compose -f docker-compose.prod.yml logs -f celery-worker

# Restart a service
docker compose -f docker-compose.prod.yml restart django

# Stop everything
docker compose -f docker-compose.prod.yml down

# Stop and remove volumes (WARNING: deletes all data)
docker compose -f docker-compose.prod.yml down -v

# Open Django shell
docker compose -f docker-compose.prod.yml exec django python manage.py shell

# Check container resource usage
docker stats
```

---

## Ports

| Service       | Internal Port | Host Port |
|---------------|--------------|-----------|
| Frontend (nginx) | 80        | 80        |
| MinIO API     | 9000         | 9000      |
| MinIO Console | 9001         | 9001      |

> Django, PostgreSQL, Redis, and Elasticsearch are internal only (not exposed to host).
