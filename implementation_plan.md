# Talktrace — Detailed Execution-Focused Implementation Plan

> Analyzed from `plan.md` on 2026-06-03  
> Stack: Django 5 + DRF + Celery | React 18 + Vite + Tailwind | PostgreSQL + pgvector + Elasticsearch | Whisper + Ollama

---

## Table of Contents

1. [Architecture Analysis & Gaps](#1-architecture-analysis--gaps)
2. [MVP vs Post-MVP Categorization](#2-mvp-vs-post-mvp-categorization)
3. [Dependency Map](#3-dependency-map)
4. [Complexity & Risk Assessment](#4-complexity--risk-assessment)
5. [Phase-Wise Implementation Plan](#5-phase-wise-implementation-plan)
6. [Recommended Development Sequence](#6-recommended-development-sequence)
7. [Scalability Considerations](#7-scalability-considerations)
8. [Demo-Ready Milestones](#8-demo-ready-milestones)
9. [Refactoring & Architecture Recommendations](#9-refactoring--architecture-recommendations)

---

## 1. Architecture Analysis & Gaps

### What the Plan Does Well
- Clean Django app separation (accounts, conversations, customers, search, analytics)
- Celery chain for AI pipeline — correct approach for sequential async tasks
- pgvector + Elasticsearch hybrid search is production-grade
- Docker Compose covers all services in one file
- UUID PKs everywhere — good for distributed system later
- shadcn/ui + Recharts is a solid, consistent frontend choice

### Missing Requirements (Critical)

| Gap | Impact | Fix |
|---|---|---|
| No WebSocket for AI status — polling every 2s burns connections | Medium | Add Django Channels + Redis channel layer, or use SSE |
| No password reset / forgot password flow | High | Add `/api/auth/password/reset/` with email token |
| No email notification for action item assignment | Medium | Add Django email + Celery task |
| No file validation on audio upload (size, type, MIME) | High | Add file size limit (50MB), accept only .mp3/.wav/.m4a/.ogg |
| No API rate limiting | High | Add `djangorestframework-throttling` per-user + per-IP |
| No refresh token rotation / blacklisting | High | Enable `ROTATE_REFRESH_TOKENS = True` in SimpleJWT |
| No multi-team / organization isolation | Medium | Add `Organization` model + tenant middleware (defer to post-MVP) |
| No CI/CD pipeline | Medium | Add GitHub Actions: lint → test → build → deploy |
| No observability (Sentry, structured logs) | Medium | Add Sentry + structlog (already in requirements, needs wiring) |
| No DB backup strategy in Docker Compose | Low | Add pg_dump cron in Makefile |
| Missing `Settings.jsx` content (profile edit + team management) | Medium | Define what admin can do vs member |
| Audio recorder: no supported format list, no max duration | Medium | Limit to 2 hours, WebM/Ogg via MediaRecorder API |
| No loading states on analytics charts | Low | Add Recharts `<Skeleton>` placeholder |
| Elasticsearch memory hard-coded at 512MB in Docker — too low for large-v3 Whisper + Ollama on same machine | High | Profile resource usage, add resource limits per service |

### Inconsistencies in the Plan

1. **`faster-whisper` container** — plan shows it as a separate Docker service but `faster-whisper` is a Python library, not a standalone HTTP service. Either run it inside the `celery-worker` container (simpler) or create a dedicated FastAPI microservice for it (more scalable but adds complexity).
   - **Recommendation**: Run inside `celery-worker` for MVP. Extract to its own FastAPI service (Week 3 or post-MVP).

2. **Ollama container** — Llama 3.1 8B requires ~8GB VRAM (GPU) or ~16GB RAM (CPU). The Docker Compose has no memory reservation. On a laptop with 16GB RAM, Ollama + Whisper + Elasticsearch + Postgres will OOM.
   - **Recommendation**: Add `mem_limit: 12g` to Ollama, `mem_limit: 8g` to Celery worker (if using Whisper there), and use OpenAI as the default for dev.

3. **`sentence-transformers` in Celery worker** — loading `all-MiniLM-L6-v2` model on every task start is slow. Must use `@app.task(bind=True)` with module-level singleton.
   - **Fix**: Load model once at worker startup using `@worker_init.connect` signal.

4. **Elasticsearch 8.x with `xpack.security.enabled=false`** — fine for dev, but plan doesn't mention enabling it for prod. Add it to Week 10 checklist.

5. **MinIO bucket creation** — plan creates a MinIO container but doesn't mention creating the bucket on first boot. Add a `minio-init` service with `mc mb` command.

6. **`cursor-based pagination`** — plan mentions it but DRF cursor pagination requires an ordering field. Confirm this is `created_at` or `interaction_date`.

7. **`zoho_sync_status` field** — added in Phase 3 but requires a migration on `conversations_conversation`. The field should be nullable/defaulted so old rows don't break.

---

## 2. MVP vs Post-MVP Categorization

### MVP — Must Have for First Working Demo

**Backend**
- [ ] Django project setup + Docker Compose (all services)
- [ ] Custom User model + JWT auth (login, register, refresh, me)
- [ ] Customer CRUD + autocomplete search
- [ ] Conversation CRUD + filters (type, date, sentiment, customer)
- [ ] ActionItem CRUD (list, update status, my-items, overdue)
- [ ] AI pipeline: LLM extraction + embedding (Whisper optional for text-only MVP)
- [ ] Polling endpoint `/api/conversations/{id}/status/`
- [ ] Keyword search via Elasticsearch (semantic and hybrid can wait)
- [ ] Analytics summary endpoint (volume, sentiment, team activity)
- [ ] Swagger docs

**Frontend**
- [ ] Login page + JWT token management
- [ ] App layout (sidebar + header)
- [ ] Dashboard with summary cards + recent conversations
- [ ] New Conversation page (text mode only for MVP — no audio)
- [ ] AI processing status with polling
- [ ] Conversation Detail view (summary, extracted fields, action items)
- [ ] Basic Search page (keyword mode, minimal filters)
- [ ] Action Items table (filter by status + mine)
- [ ] Toast notifications + loading/error states

**Infrastructure**
- [ ] Docker Compose with all services
- [ ] `make up`, `make migrate`, `make seed`, `make test` in Makefile
- [ ] Seed data command (5 customers + 20 conversations across types)

### Post-MVP — Phase 2 Additions

- Audio recording + Whisper transcription
- Semantic and hybrid search
- Customer profile + conversation timeline
- Analytics charts (full Recharts dashboard)
- Elasticsearch facets/filters endpoint
- Password reset via email
- File upload validation + progress bar

### Future Scope (Phase 3+)

- Zoho CRM bidirectional sync
- WebSocket / SSE for real-time AI status
- Multi-organization support
- Email notifications for action items
- CI/CD pipeline (GitHub Actions)
- Role-based permissions enforcement (currently just stored, not enforced)
- Competitor analytics dashboard
- Export to PDF/CSV

---

## 3. Dependency Map

```
[Docker Compose] ──────────────────────────────────────────┐
        │                                                    │
        ▼                                                    │
[DB Models + Migrations]                                     │
        │                                                    │
        ├──► [User Auth APIs] ──────────────────────────────►│
        │                                                    │
        ├──► [Customer APIs] ───────────────────────────────►│
        │           │                                        │
        └──► [Conversation APIs] ◄──────── depends on ──────┤
                    │                    Customer + User      │
                    │                                        │
                    ├──► [AI Pipeline (Celery)]              │
                    │           │                            │
                    │           ├──► [LLM Service]           │
                    │           ├──► [Embedding Service]     │
                    │           └──► [ES Indexing]           │
                    │                        │               │
                    └──► [Search APIs] ◄─────┘               │
                                │                            │
                                └──► [Analytics APIs]        │
                                                             │
[React Setup + Auth] ◄───────────────────────────────────────┘
        │
        ├──► [Dashboard] ◄── Analytics summary API
        ├──► [New Conversation] ◄── Customer autocomplete API
        │           │
        │           └──► [AI Status Poller] ◄── status API
        │
        ├──► [Conversation Detail] ◄── Conversation detail API
        ├──► [Search Page] ◄── Search API
        ├──► [Customer Profile] ◄── Customer + timeline API
        ├──► [Action Items] ◄── Action items API
        └──► [Analytics] ◄── Analytics APIs
```

**Hard dependencies** (cannot start B before A):
- `Customer APIs` → `User Auth APIs` (CustomerViewSet needs `IsAuthenticated`)
- `Conversation APIs` → `Customer APIs` (FK constraint)
- `AI Pipeline` → `Conversation APIs` (triggered on Conversation create)
- `Embedding Service` → `AI Pipeline` (runs after LLM extraction)
- `ES Indexing` → `Embedding Service` (last step in chain)
- `Search APIs` → `ES Indexing` (needs indexed documents)
- `Analytics APIs` → `Conversations` (needs data to aggregate)
- All React pages → corresponding backend API ready

---

## 4. Complexity & Risk Assessment

| Feature | Complexity | Risk | Blocker |
|---|---|---|---|
| Django project setup + Docker | Low | Low | None |
| User model + JWT auth | Low | Low | None |
| Customer + Conversation CRUD | Low-Medium | Low | Auth must be done first |
| Celery chain setup | Medium | Medium | Redis + Celery config; task order errors are hard to debug |
| Whisper transcription | Medium | **High** | GPU/CPU RAM constraints; large-v3 needs 10GB RAM on CPU |
| Ollama / LLM extraction + JSON parsing | **High** | **High** | JSON from LLM is unreliable; malformed output breaks pipeline |
| Embedding + pgvector | Medium | Low | Library well-documented; HNSW index requires manual SQL |
| Elasticsearch setup + indexing | Medium | Medium | ES config, mapping, analyzer tuning takes time |
| Hybrid search (RRF) | **High** | Medium | Score normalization + RRF merge logic is non-trivial |
| React auth + JWT interceptor | Medium | Medium | Token refresh race condition (parallel 401s) |
| Audio recorder (browser MediaRecorder) | Medium | Medium | Browser compatibility, codec support varies |
| Analytics charts (Recharts) | Low-Medium | Low | Data shape must match chart expectations |
| Zoho OAuth2 integration | **High** | **High** | Zoho API rate limits, token expiry edge cases |
| Bidirectional sync (Zoho) | **High** | **High** | Conflict resolution when Zoho record changes locally |

### Top Risks to Address Early

1. **LLM JSON reliability**: The plan relies on Ollama returning clean JSON. In practice, Llama 3.1 8B frequently adds markdown code blocks, extra text, or truncates. **Fix**: Use a strict JSON mode prompt, wrap in `json.loads()` with a regex pre-processor that strips markdown fences, and add a Pydantic validator on the output schema.

2. **Memory on dev machine**: Running Ollama (8GB) + Whisper large-v3 (3GB) + Elasticsearch (512MB) + Postgres simultaneously will exceed 16GB RAM on most laptops. **Fix**: Use OpenAI API as default in development, Ollama only in production/staging.

3. **Celery task chaining error propagation**: If `transcribe_audio` fails, the chain should stop and set `ai_status=failed`. The plan mentions this but Celery's default chain behavior swallows errors. **Fix**: Use `link_error` callbacks on each task, not just at chain level.

4. **Elasticsearch cold start**: ES 8.x takes 30-60s to become healthy on first boot. `django` and `celery-worker` must wait for it. **Fix**: Add `healthcheck` + `depends_on.condition: service_healthy` in docker-compose.

5. **JWT refresh race condition**: When multiple API calls fire simultaneously and the access token is expired, each will try to refresh independently, causing multiple refresh attempts and potential token invalidation. **Fix**: Implement a queue in the Axios interceptor (one refresh at a time, queue others).

---

## 5. Phase-Wise Implementation Plan

---

### Phase 0 — Project Bootstrap (Day 1-2, before Week 1)

Do this before anything else. These are pre-conditions for all subsequent work.

**Tasks:**
```
[ ] Create GitHub repo + branch strategy (main, develop, feature/*)
[ ] Set up pre-commit hooks: black, isort, flake8 (backend) + eslint, prettier (frontend)
[ ] Create .env.example with all required variables documented
[ ] Write root README.md with setup instructions
[ ] Confirm dev machine specs — decide Ollama vs OpenAI API for development
```

**`.env.example` variables to define now:**
```
# Django
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
POSTGRES_DB=conv_intel
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgres://postgres:postgres@postgres:5432/conv_intel

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO / S3
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=conversations
USE_MINIO=True

# AI
OLLAMA_URL=http://ollama:11434
OPENAI_API_KEY=  # fallback + dev default
LLM_PROVIDER=openai  # "ollama" or "openai"
WHISPER_MODEL=base  # Use "base" in dev, "large-v3" in prod

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200

# Email (for password reset)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
```

---

### Phase 1 — Backend Core (Weeks 1-4)

---

#### Week 1: Project Setup + Models + Docker

**Day 1-2: Django Project Scaffold**

```bash
# Commands to run
django-admin startproject config backend/
cd backend
python manage.py startapp accounts apps/accounts
python manage.py startapp conversations apps/conversations
python manage.py startapp customers apps/customers
python manage.py startapp search apps/search
python manage.py startapp analytics apps/analytics
```

**Tasks:**

```
[ ] Create backend/config/settings/base.py with:
    - INSTALLED_APPS: accounts, conversations, customers, search, analytics
    - DATABASES: psycopg3 connection with pgvector
    - REST_FRAMEWORK: default auth (JWT), pagination class
    - SIMPLE_JWT: access 60min, refresh 7 days, ROTATE_REFRESH_TOKENS=True, BLACKLIST_AFTER_ROTATION=True
    - CORS_ALLOWED_ORIGINS: ['http://localhost:5173']
    - CELERY_BROKER_URL, CELERY_RESULT_BACKEND
    - DEFAULT_FILE_STORAGE: 'storages.backends.s3boto3.S3Boto3Storage' (MinIO)

[ ] Create backend/config/settings/development.py:
    - DEBUG = True
    - EMAIL_BACKEND = console backend
    - LLM_PROVIDER = 'openai' (no Ollama locally unless powerful machine)

[ ] Create backend/config/celery.py (standard Celery app init)

[ ] Write docker-compose.yml with all services
    - Add healthchecks to postgres, redis, elasticsearch
    - Add depends_on with condition: service_healthy on django + celery-worker
    - Add minio-init service that runs: mc mb minio/conversations

[ ] Write Makefile with targets:
    make up          → docker compose up -d
    make down        → docker compose down
    make migrate     → docker exec django python manage.py migrate
    make shell       → docker exec -it django python manage.py shell
    make test        → docker exec django pytest
    make seed        → docker exec django python manage.py seed_demo_data
    make logs        → docker compose logs -f
    make worker-logs → docker compose logs -f celery-worker
```

**Models to write (in order):**

1. `apps/accounts/models.py` — `CustomUser`
```python
# Fields: id (UUID), email (unique, login), name, role (admin/manager/member)
# AUTH_USER_MODEL = 'accounts.CustomUser'
# USERNAME_FIELD = 'email'
```

2. `apps/customers/models.py` — `Customer`
```python
# Fields per schema above
# Add __str__ returning name + company
# Add index on email for autocomplete speed
```

3. `apps/conversations/models.py` — `Conversation`, `ActionItem`, `Attachment`
```python
# Conversation: all fields per schema
# topics, competitor_mentions: use django.contrib.postgres.fields.ArrayField
# embedding: pgvector.django.VectorField(dimensions=384)
# ai_status choices: PENDING, PROCESSING, COMPLETED, FAILED
# ActionItem: status + priority as TextChoices enums
# Attachment: file stored in MinIO via django-storages
```

**Migrations:**
```
[ ] python manage.py makemigrations accounts customers conversations
[ ] python manage.py migrate
[ ] Write raw SQL data migration for HNSW index:
    CREATE INDEX ON conversations_conversation
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);
    (Use RunSQL in a separate migration)
[ ] Write seed_demo_data management command:
    - 5 customers (mix of lead/contact/account types)
    - 20 conversations (mix of types, sentiments, dates spread over 90 days)
    - 30 action items (mix of status/priority)
    - Mark all conversations as ai_status=completed (bypass AI for seeding)
```

**Milestone check:** `docker compose up` starts all services. `make migrate` runs cleanly. `make seed` populates tables. Django admin at `/admin/` shows all models.

---

#### Week 2: REST APIs

**Auth (`apps/accounts/views.py + urls.py`):**
```
[ ] POST /api/auth/register/
    - Validate email unique, password min 8 chars
    - Return user data + token pair

[ ] POST /api/auth/login/
    - Uses TokenObtainPairView (SimpleJWT)
    - Add custom serializer to include user.name + user.role in response

[ ] POST /api/auth/token/refresh/
    - Uses TokenRefreshView (SimpleJWT)
    - ROTATE_REFRESH_TOKENS=True handles rotation

[ ] GET /api/auth/me/
    - Returns current user profile (id, email, name, role)

[ ] POST /api/auth/password/reset/request/   ← ADD THIS (missing from plan)
    - Sends email with reset token

[ ] POST /api/auth/password/reset/confirm/   ← ADD THIS
    - Validates token, sets new password
```

**Customers (`apps/customers/`):**
```
[ ] CustomerSerializer (id, name, email, phone, company, type, notes, created_at)
[ ] CustomerViewSet (ModelViewSet)
    - list: search with ?q= via icontains on name|email|company, pagination
    - GET /api/customers/search/?q= → returns id + name + email + company (for autocomplete)
    - GET /api/customers/{id}/timeline/ → paginated conversations for this customer
[ ] Filters: type, created_at date range
```

**Conversations (`apps/conversations/`):**
```
[ ] ConversationListSerializer (id, customer_name, type, sentiment, ai_status, created_at, summary_preview)
[ ] ConversationDetailSerializer (all fields + nested action_items + attachments)
[ ] ConversationViewSet
    - create: set ai_status=PENDING, trigger Celery chain (or mock it in Week 2)
    - list: filters via django-filter (customer, type, sentiment, date_from, date_to, created_by, ai_status)
    - retrieve: nested action items + attachments
    - GET /api/conversations/{id}/status/ → {ai_status, updated_at} (lightweight)
    - POST /api/conversations/voice/ → multipart, creates Attachment, queues pipeline
[ ] ConversationFilter class using django_filters.FilterSet
    - customer: ModelChoiceFilter
    - type: ChoiceFilter
    - sentiment: MultipleChoiceFilter  ← allows selecting multiple
    - date_from / date_to: DateFilter on interaction_date
    - created_by: ModelChoiceFilter
    - ai_status: ChoiceFilter
    - has_pending_actions: BooleanFilter (annotate with action item count)
```

**Action Items:**
```
[ ] ActionItemSerializer (id, description, assigned_to, due_date, status, priority, conversation_id)
[ ] ActionItemViewSet
    - list: filter by status, assigned_to, priority, overdue (due_date < today + status != completed)
    - GET /api/action-items/my/ → filter assigned_to = request.user
    - GET /api/action-items/overdue/ → filter due_date < today, status != completed|cancelled
    - PATCH /api/action-items/{id}/ → update status/assignee/due_date only
```

**URL Registration (`config/urls.py`):**
```python
router = DefaultRouter()
router.register('customers', CustomerViewSet)
router.register('conversations', ConversationViewSet)
router.register('action-items', ActionItemViewSet)

urlpatterns = [
    path('api/auth/', include('apps.accounts.urls')),
    path('api/', include(router.urls)),
    path('api/search/', include('apps.search.urls')),
    path('api/analytics/', include('apps.analytics.urls')),
    path('api/docs/', SpectacularSwaggerView.as_view()),
    path('api/schema/', SpectacularAPIView.as_view()),
]
```

**Testing (`tests/`):**
```
[ ] pytest.ini: DJANGO_SETTINGS_MODULE=config.settings.development
[ ] conftest.py: fixtures for user, customer, conversation, action_item
[ ] test_auth.py: register, login, refresh, me
[ ] test_customers.py: CRUD + search autocomplete
[ ] test_conversations.py: CRUD + all filters
[ ] test_action_items.py: list + my + overdue + update
[ ] Aim for 80% coverage on views
```

**Milestone check:** All endpoints return expected data. Swagger at `/api/docs/`. All pytest tests pass.

---

#### Week 3: AI Pipeline

**Important: Resource decision before starting.**
- If dev machine has <16GB RAM: use `LLM_PROVIDER=openai`, `WHISPER_MODEL=base`
- If dev machine has 32GB+ RAM: use Ollama locally

**Step-by-step:**

```
[ ] services/transcription_service.py
    class TranscriptionService:
        def __init__(self):
            model_name = settings.WHISPER_MODEL  # "base" or "large-v3"
            self._model = WhisperModel(model_name, device="cpu", compute_type="int8")

        def transcribe(self, file_path: str) -> str:
            segments, _ = self._model.transcribe(file_path, beam_size=5)
            return " ".join(s.text for s in segments)

    # Load once at module level — don't instantiate per task
    _transcription_service = TranscriptionService()

[ ] services/ai_service.py
    EXTRACTION_PROMPT = """
    You are a CRM assistant. Analyze this conversation and return ONLY a JSON object with these fields:
    {
      "summary": "...",
      "customer_requirements": "...",
      "pain_points": "...",
      "pricing_discussion": "...",
      "next_steps": "...",
      "sentiment": "very_negative|negative|neutral|positive|very_positive",
      "sentiment_score": 0.0,
      "action_items": [{"description": "...", "due_date": "YYYY-MM-DD or null", "priority": "low|medium|high"}],
      "topics": ["topic1", "topic2"],
      "competitor_mentions": ["competitor1"]
    }
    Return ONLY valid JSON. No markdown, no explanation.
    Conversation:
    {raw_text}
    """

    def extract_structured_data(raw_text: str) -> dict:
        for attempt in range(3):
            try:
                if settings.LLM_PROVIDER == 'openai':
                    response = openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(raw_text=raw_text)}],
                        response_format={"type": "json_object"},  # enforces JSON
                    )
                    text = response.choices[0].message.content
                else:  # ollama
                    # Use httpx to POST to ollama /api/generate
                    ...
                # Strip markdown code fences if present
                text = re.sub(r'^```json\s*|\s*```$', '', text.strip(), flags=re.MULTILINE)
                data = json.loads(text)
                # Validate with Pydantic model
                return ExtractionResult(**data).model_dump()
            except (json.JSONDecodeError, ValidationError) as e:
                if attempt == 2:
                    raise
                continue

[ ] services/embedding_service.py
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer('all-MiniLM-L6-v2')  # loaded once at module import

    def generate_embedding(text: str) -> list[float]:
        return _model.encode(text, normalize_embeddings=True).tolist()

[ ] tasks.py — Celery chain
    @shared_task(bind=True, max_retries=3)
    def transcribe_audio(self, conversation_id, attachment_id):
        ...
        # On failure: self.retry(countdown=60 * (2 ** self.request.retries))

    @shared_task(bind=True, max_retries=3)
    def extract_with_llm(self, conversation_id):
        ...

    @shared_task(bind=True)
    def generate_embedding(self, conversation_id):
        ...

    @shared_task(bind=True)
    def index_in_elasticsearch(self, conversation_id):
        ...

    def trigger_ai_pipeline(conversation_id, attachment_id=None):
        """Called after conversation create. Builds and launches chain."""
        tasks = []
        if attachment_id:
            tasks.append(transcribe_audio.s(conversation_id, attachment_id))
        tasks.extend([
            extract_with_llm.s(conversation_id),
            generate_embedding.s(conversation_id),
            index_in_elasticsearch.s(conversation_id),
        ])
        chain(*tasks).apply_async(
            link_error=handle_pipeline_failure.s(conversation_id)
        )

    @shared_task
    def handle_pipeline_failure(task_id, conversation_id):
        Conversation.objects.filter(id=conversation_id).update(ai_status='failed')
```

**Pydantic model for LLM output validation:**
```python
from pydantic import BaseModel, field_validator
from typing import Optional, List

class ActionItemExtracted(BaseModel):
    description: str
    due_date: Optional[str] = None
    priority: str = "medium"

class ExtractionResult(BaseModel):
    summary: str
    customer_requirements: str = ""
    pain_points: str = ""
    pricing_discussion: str = ""
    next_steps: str = ""
    sentiment: str
    sentiment_score: float
    action_items: List[ActionItemExtracted] = []
    topics: List[str] = []
    competitor_mentions: List[str] = []

    @field_validator('sentiment')
    def validate_sentiment(cls, v):
        allowed = {'very_negative', 'negative', 'neutral', 'positive', 'very_positive'}
        return v if v in allowed else 'neutral'

    @field_validator('sentiment_score')
    def clamp_score(cls, v):
        return max(-1.0, min(1.0, float(v)))
```

**Milestone check:** POST a conversation text → Celery worker logs show all 4 tasks completing → GET conversation detail shows summary + action items populated → ai_status = completed.

---

#### Week 4: Search

**Elasticsearch Setup:**
```
[ ] Create ES index on app startup (use AppConfig.ready() in search app)
    mapping = {
        "mappings": {
            "properties": {
                "conversation_id": {"type": "keyword"},
                "customer_id": {"type": "keyword"},
                "customer_name": {"type": "text", "analyzer": "standard"},
                "raw_text": {"type": "text", "analyzer": "english"},
                "ai_summary": {"type": "text", "analyzer": "english", "boost": 2.0},
                "customer_requirements": {"type": "text", "analyzer": "english"},
                "pain_points": {"type": "text", "analyzer": "english"},
                "next_steps": {"type": "text", "analyzer": "english"},
                "topics": {"type": "keyword"},
                "competitor_mentions": {"type": "keyword"},
                "conversation_type": {"type": "keyword"},
                "sentiment": {"type": "keyword"},
                "interaction_date": {"type": "date"},
                "created_by_id": {"type": "keyword"},
            }
        }
    }
```

**search_service.py:**
```python
def keyword_search(query, filters, page=1, page_size=20):
    body = {
        "query": {
            "bool": {
                "must": [{
                    "multi_match": {
                        "query": query,
                        "fields": ["ai_summary^2", "raw_text", "customer_requirements", "pain_points", "next_steps"],
                        "type": "best_fields",
                        "fuzziness": "AUTO"
                    }
                }],
                "filter": _build_es_filters(filters)
            }
        },
        "highlight": {
            "fields": {"ai_summary": {}, "raw_text": {"fragment_size": 150}}
        },
        "from": (page - 1) * page_size,
        "size": page_size
    }
    return es_client.search(index=CONVERSATIONS_INDEX, body=body)

def semantic_search(query, filters, page=1, page_size=20):
    query_embedding = generate_embedding(query)
    # Use pgvector cosine similarity
    qs = Conversation.objects.annotate(
        similarity=CosineDistance('embedding', query_embedding)
    ).filter(
        embedding__isnull=False,
        **_build_django_filters(filters)
    ).order_by('similarity')
    return qs[((page-1)*page_size):(page*page_size)]

def hybrid_search(query, filters, page=1, page_size=20):
    # Run both in parallel using concurrent.futures
    with ThreadPoolExecutor(max_workers=2) as executor:
        kw_future = executor.submit(keyword_search, query, filters, page=1, page_size=100)
        sem_future = executor.submit(semantic_search, query, filters, page=1, page_size=100)
        kw_results = kw_future.result()
        sem_results = sem_future.result()

    # Reciprocal Rank Fusion (k=60)
    scores = {}
    for rank, hit in enumerate(kw_results['hits']['hits'], 1):
        cid = hit['_source']['conversation_id']
        scores[cid] = scores.get(cid, 0) + 1 / (60 + rank)
    for rank, conv in enumerate(sem_results, 1):
        cid = str(conv.id)
        scores[cid] = scores.get(cid, 0) + 1 / (60 + rank)

    # Sort by combined score, return top page_size
    sorted_ids = sorted(scores, key=scores.get, reverse=True)
    page_ids = sorted_ids[((page-1)*page_size):(page*page_size)]
    return Conversation.objects.filter(id__in=page_ids)

[ ] GET /api/search/ endpoint with query params
[ ] GET /api/search/filters/ → returns available facets with counts from ES aggregations
[ ] Management command: python manage.py reindex_elasticsearch
    - Iterates all conversations with ai_status=completed
    - Indexes each in batches of 100
[ ] Add index_in_elasticsearch task as final step in AI pipeline
```

**Milestone check:** Keyword search returns highlighted results. Semantic search returns conceptually similar results. Hybrid search combines both.

---

### Phase 2 — React Frontend (Weeks 5-8)

---

#### Week 5: Setup + Auth + Layout + Dashboard

**Project initialization:**
```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install react-router-dom axios zustand @tanstack/react-query recharts tailwindcss clsx tailwind-merge lucide-react react-hot-toast date-fns
npx tailwindcss init -p
npx shadcn-ui@latest init
```

**Tasks:**

```
[ ] vite.config.js: add proxy for /api → http://localhost:8000 (avoids CORS in dev)

[ ] api/client.js — Axios instance:
    - baseURL: /api (proxied)
    - Request interceptor: add Authorization: Bearer {accessToken}
    - Response interceptor:
      - On 401: check if it's a refresh request (avoid infinite loop)
      - If not: pause queue, call /api/auth/token/refresh/ once
      - On success: retry all queued requests with new token
      - On refresh failure: clear tokens, redirect to /login
      - Use a isRefreshing flag + failedQueue array to prevent parallel refresh calls

[ ] store/authStore.js (Zustand):
    - State: user, accessToken, refreshToken, isAuthenticated
    - Actions: login(email, pass), logout(), setTokens(), loadFromStorage()
    - Persist to localStorage

[ ] Login.jsx:
    - Email + password form with validation
    - Show error on invalid credentials
    - Redirect to / on success
    - "Remember me" checkbox (extend refresh token TTL)

[ ] Router.jsx:
    - <Routes> with ProtectedRoute wrapper
    - ProtectedRoute: checks isAuthenticated, redirects to /login if not

[ ] AppLayout.jsx:
    - Collapsible sidebar (default open on desktop, closed on mobile)
    - Sidebar links: Dashboard, New Conversation, Search, Customers, Action Items, Analytics, Settings
    - Active link highlighting via useMatch
    - User menu in header: name, role badge, logout

[ ] Dashboard.jsx:
    - 4 summary cards: Total Conversations, Pending Actions, Avg Sentiment, Active Customers
    - Data from GET /api/analytics/summary/
    - Recent 10 conversations list (customer name, type, sentiment badge, date)
    - "New Conversation" CTA button
    - Loading skeleton for cards
```

**Milestone check:** Login works end-to-end. Sidebar navigates between routes. Dashboard shows live API data with skeletons during load.

---

#### Week 6: Conversation Capture + Detail

```
[ ] hooks/useDebounce.js (300ms default)

[ ] components/customers/CustomerSearch.jsx:
    - Controlled input with useDebounce
    - Calls GET /api/customers/search/?q=
    - Shows dropdown of matches (name + company)
    - On select: sets customer ID in form

[ ] components/conversations/AudioRecorder.jsx:
    - Request mic permission on mount (navigator.mediaDevices.getUserMedia)
    - Show permission denied error if blocked
    - MediaRecorder API with mimeType: 'audio/webm'
    - Visual timer (MM:SS) during recording
    - Stop → create Blob → call onRecordingComplete(blob)
    - Max recording: 2 hours (auto-stop)

[ ] pages/NewConversation.jsx:
    - Step 1: Select/create customer (CustomerSearch + "Add new customer" inline modal)
    - Step 2: Conversation type (radio buttons with icons)
    - Step 3: Date/time picker (defaults to now)
    - Step 4: Content tabs:
      - Text tab: structured textareas (what was discussed? requirements? next steps?) + raw text field
      - Voice tab: AudioRecorder component
    - Submit button → POST /api/conversations/ or /api/conversations/voice/
    - On success: navigate to /conversations/{id}

[ ] components/conversations/AIProcessingStatus.jsx:
    - Polls GET /api/conversations/{id}/status/ every 2 seconds
    - Shows step-by-step progress:
      Step 1: "Transcribing audio..." (if voice)
      Step 2: "Analyzing conversation..."
      Step 3: "Generating summary..."
      Step 4: "Building search index..."
    - Animated spinner + step checkmarks
    - On ai_status=completed: trigger parent refresh, hide component
    - On ai_status=failed: show error + "Retry" button

[ ] components/conversations/SentimentBadge.jsx:
    - very_negative: red pill
    - negative: orange pill
    - neutral: gray pill
    - positive: green pill
    - very_positive: emerald pill
    - Show sentiment_score as tooltip

[ ] pages/ConversationDetail.jsx:
    - GET /api/conversations/{id}/
    - Show AIProcessingStatus if ai_status != completed|failed
    - Two-column layout (desktop) / stacked (mobile):
      Left: raw text / transcript (scrollable, monospace)
      Right:
        - AI Summary card
        - Customer Requirements card (collapsible)
        - Pain Points card (collapsible)
        - Pricing Discussion card (collapsible)
        - Next Steps card (collapsible)
    - Sentiment badge + score + topics chips + competitor chips
    - Action Items section: list with inline status toggle (PATCH /api/action-items/{id}/)
    - Edit button → inline form for raw_text (if ai_status=failed, allow re-submit)
```

**Milestone check:** Complete flow: fill form → submit → see processing animation → summary + action items appear automatically.

---

#### Week 7: Search + Customer Profile

```
[ ] components/search/SearchModeToggle.jsx:
    - Three buttons: Keyword | Semantic | Hybrid (Hybrid default)
    - Keyboard shortcut: Alt+K, Alt+S, Alt+H

[ ] components/search/FilterSidebar.jsx:
    - Customer dropdown (multiselect)
    - Date range (from + to date pickers)
    - Sentiment checkboxes (5 options)
    - Conversation type multiselect
    - "Has pending actions" toggle
    - Topics multiselect (populated from /api/search/filters/)
    - Clear all filters button
    - Filter count badge on sidebar toggle

[ ] components/search/ResultCard.jsx:
    - Customer name + type badge + date
    - Highlighted snippet from ai_summary or raw_text
    - Sentiment badge
    - Topic chips
    - Click → navigate to /conversations/{id}

[ ] pages/SearchPage.jsx:
    - Sticky search bar at top
    - SearchModeToggle below bar
    - FilterSidebar (collapsible on mobile)
    - Infinite scroll OR traditional pagination for results
    - Result count display ("243 conversations found")
    - Empty state with illustration + "try different keywords"
    - useSearch hook: manages query state + debounce + API call

[ ] hooks/useSearch.js:
    - State: query, mode, filters, results, loading, error, page
    - 500ms debounce on query
    - Resets to page 1 on filter change
    - Uses React Query for caching

[ ] components/customers/CustomerTimeline.jsx:
    - Chronological conversation list for one customer
    - Each entry: date, type icon, sentiment badge, summary preview
    - Sentiment sparkline: mini Recharts line chart of sentiment_score over time

[ ] pages/CustomerProfile.jsx:
    - Customer header: name, company, email, phone, type badge
    - Stats: total conversations, last contact date, avg sentiment
    - CustomerTimeline below
    - Edit customer info inline
```

**Milestone check:** Search returns paginated results across all 3 modes with filters applied. Customer profile shows full timeline with sentiment trend.

---

#### Week 8: Action Items + Analytics + Polish

```
[ ] pages/ActionItems.jsx:
    - Table with columns: Description, Customer, Conversation, Assigned To, Due Date, Priority, Status
    - Sortable columns (click header)
    - Filter tabs: All | My Items | Overdue | By Status
    - Inline status update (dropdown in table row)
    - Inline assignee update (user picker)
    - Due date color coding: overdue=red, due today=orange, future=normal
    - Bulk status update (checkboxes + bulk action dropdown)

[ ] components/analytics/VolumeChart.jsx:
    - Recharts ComposedChart: Bar for volume + Line for trend
    - Time grouping: Day | Week | Month (radio)
    - Tooltip: exact count on hover

[ ] components/analytics/SentimentTrend.jsx:
    - Recharts AreaChart: stacked areas per sentiment level
    - Color-coded: red/orange/gray/green/emerald
    - Time axis

[ ] components/analytics/TeamActivity.jsx:
    - Recharts HorizontalBarChart: one bar per team member
    - Shows conversations captured this period

[ ] components/analytics/TopicCloud.jsx:
    - Recharts HorizontalBarChart sorted by frequency
    - Top 10 topics
    - Click topic → opens SearchPage filtered by that topic

[ ] components/analytics/FollowUpRate.jsx:
    - Recharts PieChart/RadialBarChart
    - Completed vs Pending vs Overdue action items

[ ] pages/Analytics.jsx:
    - Date range selector at top (last 7d | 30d | 90d | custom)
    - 2x3 grid of chart components (responsive)
    - All charts re-fetch on date range change

[ ] Polish pass:
    - Add loading skeletons to all data-loading components
    - Add error boundaries (catch unexpected React errors)
    - Add 404 page for unknown routes
    - Responsive: test at 1024px, 1280px, 1440px
    - Add keyboard navigation to sidebar
    - Page titles (document.title) per route
    - Favicon + app manifest

[ ] react-hot-toast setup:
    - Success toast on conversation saved
    - Error toast on API failures
    - Info toast "AI processing started..."
```

**Milestone check:** Core platform complete. Every page works end-to-end with live data.

---

### Phase 3 — Zoho CRM Integration (Weeks 9-10)

---

#### Week 9: Zoho Sync Service

```
[ ] Create apps/zoho/ Django app

[ ] apps/zoho/models.py:
    - ZohoSyncLog(conversation_id, zoho_note_id, zoho_task_id, synced_at, status, error_message)

[ ] apps/zoho/oauth.py:
    - ZohoOAuthManager class
    - Reads ZOHO_REFRESH_TOKEN from env (manually generated once via OAuth consent screen)
    - Maintains access token in Redis with TTL
    - auto_refresh(): fetches new access token before expiry
    - get_headers(): returns {"Authorization": f"Zoho-oauthtoken {access_token}"}

[ ] apps/zoho/services.py:
    - ZohoAPIClient with rate limiting (token bucket: 100 req/min)
    - get_contacts(modified_after=None) → paginated Zoho contact list
    - create_note(record_id, module, content) → Zoho Notes API
    - create_task(subject, due_date, description, related_to) → Zoho Tasks API
    - exponential_backoff_retry(func, max_retries=3)

[ ] apps/zoho/tasks.py:
    - sync_zoho_contacts_to_local() → Celery periodic task (every 1 hour)
      - Calls Bulk Read API for Contacts/Accounts
      - Upserts into customers_customer using zoho_record_id
    - sync_conversation_to_zoho(conversation_id) → triggered after AI pipeline
      - Creates Note on linked Zoho Contact with formatted summary
      - Creates Tasks for each action item
      - Updates zoho_sync_status on Conversation

[ ] Add to Conversation model:
    - zoho_sync_status: CharField choices (not_applicable, pending, synced, failed)
    - Default: not_applicable (when no zoho_record_id on customer)

[ ] Register Celery beat schedule for sync_zoho_contacts_to_local every hour

[ ] Dead-letter queue: failed Zoho syncs → store in ZohoSyncLog with error, retry up to 3x
```

#### Week 10: Zoho UI + Testing + Deployment

```
[ ] Frontend: Zoho sync status badge on ConversationDetail
    - Show: "Synced to Zoho ✓" / "Sync pending" / "Sync failed - Retry"
    - Retry button calls POST /api/zoho/sync/{conversation_id}/retry/

[ ] Frontend: Sync health panel on Settings page (admin only)
    - Last sync time for Zoho contacts
    - Count of failed syncs
    - "Sync now" button

[ ] E2E test:
    - Capture conversation → AI processes → check Zoho CRM has Note + Task created

[ ] docker-compose.prod.yml:
    - Replace manage.py runserver with gunicorn
    - Add nginx service as reverse proxy + static file server
    - Add certbot for SSL (or document manual cert process)
    - Set DEBUG=False, ALLOWED_HOSTS=your-domain.com

[ ] Security pre-deployment:
    - Verify CORS restricted to frontend domain only
    - Verify JWT secret is strong and in env (not in code)
    - Test file upload: reject non-audio files, reject >50MB
    - Verify SQL injection not possible (DRF + ORM handles this, but check raw queries)
    - Enable Elasticsearch security for prod (username + password)
    - Add Django SECURE_* settings (HSTS, secure cookies, etc.)

[ ] Load test: locust or k6
    - 50 concurrent users submitting conversations
    - Monitor Celery queue depth, Postgres connection pool, ES indexing lag

[ ] Deploy to staging (document exact steps in README)
```

---

## 6. Recommended Development Sequence

Follow this exact order to avoid blockers:

```
Week 1:  Docker Compose → Django project → Models → Migrations → Seed data
Week 2:  JWT Auth → Customer API → Conversation API → Action Item API → Tests
Week 3:  Celery config → LLM service → Embedding service → Celery chain → Status polling
Week 4:  ES setup → Keyword search → Semantic search → Hybrid search → Reindex command
Week 5:  Vite setup → Axios client → Auth store → Login → Layout → Dashboard
Week 6:  CustomerSearch → CaptureForm → AudioRecorder → ProcessingStatus → Detail view
Week 7:  SearchPage → Filter sidebar → CustomerProfile → Timeline → Sparkline
Week 8:  ActionItems table → Analytics charts → Responsive pass → Error states → Polish
Week 9:  Zoho OAuth → Contact sync → Note/Task creation → Sync status model
Week 10: Zoho UI → E2E tests → Prod docker-compose → Security review → Staging deploy
```

**When to deviate:**
- If Ollama is too slow in dev: switch to OpenAI immediately (don't burn days debugging)
- If ES is overkill for the demo: defer to Week 5, use only pgvector for initial search
- If audio recording is unreliable in browser tests: complete all text-mode features first

---

## 7. Scalability Considerations

### What Scales Well As-Is
- PostgreSQL + pgvector: handles millions of rows with proper indexing
- Celery + Redis: horizontal worker scaling (just add more `celery-worker` containers)
- Elasticsearch: already clusterable (add more nodes)
- Stateless Django: can run behind load balancer immediately

### What Needs Attention at Scale

| Issue | When It Hits | Solution |
|---|---|---|
| Sentence-transformers model loaded per worker | 4+ workers on same machine | Use a shared embedding microservice (FastAPI + /embed endpoint) |
| Whisper model loaded per worker | 2+ workers | Same: dedicated transcription microservice |
| PostgreSQL connection pool exhaustion | 50+ concurrent users | Add PgBouncer between Django and Postgres |
| ES single-node memory | 1M+ documents | Switch to ES cluster or use OpenSearch |
| Celery task queue grows unbounded | 1000+ submissions/day | Add priority queues: `high` for new submissions, `low` for re-indexing |
| Redis single-node | 10K+ requests/day | Add Redis Sentinel for HA, or Redis Cluster |
| MinIO single instance | >1TB of audio | Switch to distributed MinIO or use S3 directly |
| Analytics queries slow at scale | 100K+ conversations | Materialize analytics via Celery beat (cache results every 15 min) |

### Multi-Tenancy (Post-MVP)
The current schema has no `organization_id`. Adding it later requires:
- `Organization` model
- FK on `User`, `Customer`, `Conversation`
- Tenant middleware that filters all querysets by `request.user.organization`
- This is a significant migration — design for it early if multi-team support is needed at launch

---

## 8. Demo-Ready Milestones

These are specific checkpoints for showing the product to stakeholders:

### Demo 1: Core Backend (End of Week 2)
**Show:** Swagger UI with all working endpoints. Postman collection walking through: create customer → create conversation → list conversations with filters → update action item.
**Duration:** 10 minutes.

### Demo 2: AI Pipeline (End of Week 3)
**Show:** Submit a real conversation text → wait 15-30s → refresh → show the structured summary, extracted action items, sentiment score, topics extracted. Run it twice with different conversation types.
**Duration:** 15 minutes.

### Demo 3: Working Product (End of Week 6)
**Show:** Full browser flow. Login → Dashboard → New Conversation → type something real → watch the AI processing animation → Conversation Detail with all AI insights. Capture a second conversation for the same customer.
**Duration:** 20 minutes.

### Demo 4: Complete Platform (End of Week 8)
**Show:** Search across multiple conversations (keyword + semantic). Customer profile with timeline. Action items board. Analytics charts. Demonstrate a full sales conversation capture workflow.
**Duration:** 30 minutes.

### Demo 5: Production-Ready (End of Week 10)
**Show:** Same as Demo 4 but on staging URL. Capture a conversation → show it appear in Zoho CRM as a Note within 60 seconds. Show sync health panel.
**Duration:** 30 minutes.

---

## 9. Refactoring & Architecture Recommendations

### Immediate (Before Starting Development)

1. **Use `LLM_PROVIDER` env var everywhere** — never hardcode Ollama or OpenAI. The `ai_service.py` must check this setting, so swapping providers is a config change, not a code change.

2. **Create a `Pydantic` schema for LLM output** (shown in Week 3 above) — do this before writing the extraction service. It will catch malformed LLM outputs and save significant debugging time.

3. **Define API response schemas in DRF serializers before writing views** — write the serializer, check the output in Django shell, then write the view. Prevents shape mismatches with frontend.

### Short-Term (During Development)

4. **Wrap all Celery tasks in try/except with structured logging** — use `structlog` (already in requirements) to log task_id, conversation_id, duration, and error. This makes debugging the AI pipeline much faster.

5. **Don't use `django.test.TestCase` — use `pytest-django` fixtures** — the plan already says pytest, just make sure DRF `APIClient` is used not the built-in test client.

6. **React Query for all server state, Zustand only for client state** — the plan mentions both. Use React Query for all API data (conversations, customers, search results). Use Zustand only for auth tokens and UI state (sidebar open/closed). Don't duplicate server data in Zustand.

### Post-MVP Refactoring (When Needed)

7. **Extract AI services into a separate FastAPI microservice** — when the celery worker needs to scale independently from the Django app, having Whisper + sentence-transformers in a dedicated service with its own Docker image is cleaner.

8. **Add cursor pagination everywhere** — the plan mentions it but `CursorPagination` requires careful ordering. Start with `LimitOffsetPagination` for simplicity, migrate to cursor when you have 10K+ rows.

9. **Materialize analytics** — currently all analytics endpoints run aggregation queries on-demand. At 50K+ conversations, add a `AnalyticsSnapshot` model that Celery beat populates every 15 minutes.

10. **Add Django Channels for WebSocket** — replace the 2s polling on AI status with a WebSocket push. This is optional for MVP but improves UX significantly. Requires adding `daphne` or `uvicorn` as the ASGI server and a separate `channels_worker` container.

---

## Quick Reference: What to Build First, What to Delay, What is Future Scope

| Feature | Build When | Reason |
|---|---|---|
| Docker Compose + Django models | Day 1 | Unblocks everything |
| JWT Auth | Week 1 | Needed for all APIs |
| Customer + Conversation CRUD | Week 1-2 | Core data layer |
| OpenAI LLM extraction (text) | Week 3 | Use OpenAI, not Ollama, for speed |
| Keyword search (Elasticsearch) | Week 4 | Core feature |
| React auth + dashboard | Week 5 | Needed to show anything |
| Capture form (text only) | Week 6 | Core workflow |
| Conversation detail | Week 6 | Needed to show AI output |
| **Audio recording + Whisper** | Week 6-7 | After text flow is proven |
| **Semantic + hybrid search** | Week 4-7 | After ES keyword works |
| Action items table | Week 8 | Important but not blocking demo |
| Analytics charts | Week 8 | Nice-to-have for first demo |
| Password reset | Week 8 | Required for real users |
| Zoho integration | Week 9-10 | Phase 3, not MVP |
| Multi-organization support | Post-MVP | Big schema change, needs design |
| WebSocket AI status | Post-MVP | Polling works fine for MVP |
| Email notifications | Post-MVP | Nice-to-have |
| CI/CD pipeline | Post-MVP | Set up after first deployment |
| Load testing | Week 10 | Before staging deployment |
