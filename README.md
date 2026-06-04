# Talktrace — CRM Conversation Intelligence

Capture, transcribe, and AI-analyze sales and support conversations. Auto-extract summaries, action items, sentiment, and sync to Zoho CRM.

## Stack

- **Backend**: Django 5 + DRF + Celery
- **Frontend**: React 18 + Vite + TailwindCSS
- **Database**: PostgreSQL 16 + pgvector
- **Search**: Elasticsearch 8 (keyword + semantic + hybrid)
- **AI**: Whisper (STT) + Ollama/OpenAI (LLM) + sentence-transformers (embeddings)
- **Storage**: MinIO (S3-compatible)

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd talktrace
cp .env.example .env
# Edit .env — set your OPENAI_API_KEY
```

### 2. Start all services

```bash
make build   # First time only
make up
make migrate
make seed    # Load demo data
```

### 3. Access

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Django API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/api/docs/ |
| Django Admin | http://localhost:8000/admin/ |
| MinIO Console | http://localhost:9001 |
| Elasticsearch | http://localhost:9200 |

### 4. Create admin user

```bash
make createsuperuser
```

## Development Commands

```bash
make up           # Start all containers
make down         # Stop all containers
make migrate      # Run DB migrations
make seed         # Load demo data
make test         # Run test suite
make test-cov     # Tests with coverage report
make shell        # Django shell
make logs         # All container logs
make worker-logs  # Celery worker logs
make reindex      # Re-index Elasticsearch
make lint         # flake8 lint check
make format       # black + isort
```

## Environment Variables

See `.env.example` for all configuration options.

Key settings:
- `LLM_PROVIDER`: `openai` (dev) or `ollama` (prod with GPU)
- `WHISPER_MODEL`: `base` (dev) or `large-v3` (prod)
- `OPENAI_API_KEY`: Required when `LLM_PROVIDER=openai`

## Project Structure

```
talktrace/
├── backend/          # Django project
│   ├── config/       # Settings, celery, urls
│   └── apps/         # accounts, conversations, customers, search, analytics
├── frontend/         # React + Vite
│   └── src/          # Components, pages, hooks, api
├── docker-compose.yml
├── Makefile
└── .env.example
```

## API Documentation

Swagger UI available at http://localhost:8000/api/docs/ after starting the server.

## Phases

- **Phase 1** (Weeks 1-4): Backend — models, APIs, AI pipeline, search
- **Phase 2** (Weeks 5-8): Frontend — all pages and charts
- **Phase 3** (Weeks 9-10): Zoho CRM sync + production deploy
