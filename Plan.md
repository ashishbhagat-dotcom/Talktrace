# CRM Conversation Intelligence — Implementation Plan

> **Approach:** Build core platform first (Django + React), integrate Zoho CRM later
> **Backend:** Django + Django REST Framework + Celery
> **Frontend:** React + Vite + TailwindCSS
> **Timeline:** 10 weeks to working platform, Zoho integration as Phase 3

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                         │
│              React + Vite + Tailwind                │
│                                                     │
│  ┌───────────┐ ┌──────────┐ ┌────────────────────┐ │
│  │ Capture   │ │ Search   │ │ Analytics          │ │
│  │ Form      │ │ + Filter │ │ Dashboard          │ │
│  └─────┬─────┘ └────┬─────┘ └────────┬───────────┘ │
│        └─────────────┼────────────────┘             │
└──────────────────────┼──────────────────────────────┘
                       │ REST API (JWT Auth)
┌──────────────────────┼──────────────────────────────┐
│                    BACKEND                          │
│             Django + DRF + Celery                   │
│                                                     │
│  ┌──────────────┐ ┌────────────┐ ┌───────────────┐ │
│  │ Conversation │ │ AI Service │ │ Search        │ │
│  │ API          │ │ (Celery)   │ │ Service       │ │
│  └──────┬───────┘ └─────┬──────┘ └───────┬───────┘ │
│         │               │                │         │
│  ┌──────┴───────────────┴────────────────┴───────┐ │
│  │        PostgreSQL 16 + pgvector               │ │
│  └───────────────────────────────────────────────┘ │
│         │               │                          │
│  ┌──────┴──────┐ ┌──────┴──────┐                   │
│  │ Redis       │ │ Elasticsearch│                   │
│  │ (Queue)     │ │ (Full-text)  │                   │
│  └─────────────┘ └──────────────┘                   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ AI Stack                                     │   │
│  │ Whisper (STT) + Ollama/OpenAI (LLM)         │   │
│  │ + sentence-transformers (Embeddings)          │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Why |
|---|---|---|
| Backend Framework | Django 5.x + DRF | Batteries-included, ORM, admin panel, mature ecosystem |
| Task Queue | Celery + Redis | Async AI pipeline, background jobs |
| Database | PostgreSQL 16 + pgvector | Structured data + vector search in one DB |
| Full-Text Search | Elasticsearch 8.x | BM25 relevance, highlighting, faceted search |
| Speech-to-Text | faster-whisper (large-v3) | 4x faster than standard Whisper, runs locally |
| LLM | Ollama (Llama 3.1 8B) / OpenAI GPT-4o-mini | Summarization, extraction, sentiment |
| Embeddings | all-MiniLM-L6-v2 | 384-dim vectors, fast, lightweight |
| Object Storage | MinIO | S3-compatible, self-hosted for audio files |
| Frontend | React 18 + Vite | Fast dev server, modern tooling |
| Styling | TailwindCSS + shadcn/ui | Utility-first, consistent design system |
| State Management | Zustand or React Query | Lightweight, server-state focused |
| Charts | Recharts | React-native charting, composable |
| Containerization | Docker Compose | Single command to run everything |

---

## Project Structure

```
crm-conversation-intelligence/
│
├── backend/
│   ├── config/                     # Django project settings
│   │   ├── settings/
│   │   │   ├── base.py             # Shared settings
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── celery.py               # Celery app config
│   │   └── wsgi.py
│   │
│   ├── apps/
│   │   ├── accounts/               # User auth + management
│   │   │   ├── models.py           # Custom User model
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   ├── urls.py
│   │   │   └── permissions.py
│   │   │
│   │   ├── conversations/          # Core conversation module
│   │   │   ├── models.py           # Conversation, ActionItem, Attachment
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   ├── urls.py
│   │   │   ├── filters.py          # django-filter classes
│   │   │   ├── tasks.py            # Celery tasks (AI pipeline)
│   │   │   └── services/
│   │   │       ├── ai_service.py       # LLM summarization + extraction
│   │   │       ├── embedding_service.py # Vector embedding generation
│   │   │       ├── transcription_service.py  # Whisper STT
│   │   │       └── search_service.py   # ES + pgvector search
│   │   │
│   │   ├── search/                 # Search endpoints
│   │   │   ├── views.py
│   │   │   ├── urls.py
│   │   │   └── services.py         # Hybrid search (RRF)
│   │   │
│   │   ├── analytics/              # Dashboard data endpoints
│   │   │   ├── views.py
│   │   │   ├── urls.py
│   │   │   └── services.py
│   │   │
│   │   └── customers/              # Customer/contact records
│   │       ├── models.py           # Customer model (later syncs from Zoho)
│   │       ├── serializers.py
│   │       ├── views.py
│   │       └── urls.py
│   │
│   ├── common/                     # Shared utilities
│   │   ├── pagination.py           # Cursor pagination
│   │   ├── exceptions.py           # Custom exception handler
│   │   └── middleware.py
│   │
│   ├── requirements/
│   │   ├── base.txt
│   │   ├── development.txt
│   │   └── production.txt
│   │
│   ├── Dockerfile
│   └── manage.py
│
├── frontend/
│   ├── src/
│   │   ├── api/                    # Axios instance + API functions
│   │   │   ├── client.js           # Axios config with JWT interceptor
│   │   │   ├── conversations.js
│   │   │   ├── search.js
│   │   │   ├── analytics.js
│   │   │   ├── customers.js
│   │   │   └── auth.js
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn/ui base components
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.jsx
│   │   │   │   ├── Header.jsx
│   │   │   │   └── AppLayout.jsx
│   │   │   ├── conversations/
│   │   │   │   ├── CaptureForm.jsx
│   │   │   │   ├── ConversationCard.jsx
│   │   │   │   ├── ConversationDetail.jsx
│   │   │   │   ├── ActionItemList.jsx
│   │   │   │   ├── SentimentBadge.jsx
│   │   │   │   ├── AudioRecorder.jsx
│   │   │   │   └── AIProcessingStatus.jsx
│   │   │   ├── search/
│   │   │   │   ├── SearchBar.jsx
│   │   │   │   ├── FilterSidebar.jsx
│   │   │   │   ├── ResultCard.jsx
│   │   │   │   └── SearchModeToggle.jsx
│   │   │   ├── analytics/
│   │   │   │   ├── VolumeChart.jsx
│   │   │   │   ├── SentimentTrend.jsx
│   │   │   │   ├── TeamActivity.jsx
│   │   │   │   ├── TopicCloud.jsx
│   │   │   │   └── FollowUpRate.jsx
│   │   │   └── customers/
│   │   │       ├── CustomerSearch.jsx
│   │   │       └── CustomerTimeline.jsx
│   │   │
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── NewConversation.jsx
│   │   │   ├── ConversationView.jsx
│   │   │   ├── SearchPage.jsx
│   │   │   ├── CustomerProfile.jsx
│   │   │   ├── ActionItems.jsx
│   │   │   ├── Analytics.jsx
│   │   │   ├── Login.jsx
│   │   │   └── Settings.jsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useAuth.js
│   │   │   ├── useConversations.js
│   │   │   ├── useSearch.js
│   │   │   └── useDebounce.js
│   │   │
│   │   ├── store/                  # Zustand stores
│   │   │   ├── authStore.js
│   │   │   └── uiStore.js
│   │   │
│   │   ├── utils/
│   │   │   ├── formatters.js
│   │   │   └── constants.js
│   │   │
│   │   ├── App.jsx
│   │   ├── Router.jsx
│   │   └── main.jsx
│   │
│   ├── Dockerfile
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
│
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── Makefile                        # Shortcuts: make up, make migrate, make test
└── README.md
```

---

## Database Schema

### `accounts_user`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | `default=uuid4` |
| email | VARCHAR(255) UNIQUE | Login identifier |
| name | VARCHAR(150) | Display name |
| role | VARCHAR(20) | admin / manager / member |
| is_active | BOOLEAN | |
| date_joined | TIMESTAMP | |

### `customers_customer`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(255) | Company or person name |
| email | VARCHAR(255) | Primary contact email |
| phone | VARCHAR(50) | |
| company | VARCHAR(255) | Organization name |
| type | VARCHAR(20) | lead / contact / account |
| notes | TEXT | Internal notes about this customer |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| zoho_record_id | VARCHAR(50) NULL | Placeholder for future Zoho sync |

### `conversations_conversation`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| customer | FK → Customer | Linked customer record |
| conversation_type | VARCHAR(20) | phone_call / in_person / video_call / whatsapp / email / other |
| raw_text | TEXT | Full original text or transcript |
| ai_summary | TEXT NULL | LLM-generated summary |
| customer_requirements | TEXT NULL | Extracted requirements |
| pain_points | TEXT NULL | Extracted pain points |
| pricing_discussion | TEXT NULL | Extracted pricing content |
| next_steps | TEXT NULL | Extracted follow-ups |
| sentiment | VARCHAR(20) NULL | very_negative → very_positive |
| sentiment_score | FLOAT NULL | -1.0 to 1.0 |
| topics | ArrayField(VARCHAR) | Detected topic tags |
| competitor_mentions | ArrayField(VARCHAR) | Competitor names |
| embedding | VectorField(384) NULL | pgvector embedding |
| ai_status | VARCHAR(20) | pending / processing / completed / failed |
| created_by | FK → User | Who captured this |
| interaction_date | DATETIME | When the conversation happened |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### `conversations_actionitem`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| conversation | FK → Conversation | |
| description | TEXT | |
| assigned_to | FK → User NULL | |
| due_date | DATE NULL | |
| status | VARCHAR(20) | pending / in_progress / completed / cancelled |
| priority | VARCHAR(10) | low / medium / high / urgent |
| created_at | TIMESTAMP | |

### `conversations_attachment`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| conversation | FK → Conversation | |
| file_type | VARCHAR(20) | audio / image / document / recording |
| file | FileField | Stored in MinIO/S3 |
| original_filename | VARCHAR(255) | |
| transcription | TEXT NULL | Whisper output for audio |
| created_at | TIMESTAMP | |

### Indexes

```python
# In Conversation model Meta or via migration
indexes = [
    models.Index(fields=['customer']),
    models.Index(fields=['created_by']),
    models.Index(fields=['interaction_date']),
    models.Index(fields=['sentiment']),
    models.Index(fields=['ai_status']),
    GinIndex(fields=['topics']),
    GinIndex(fields=['competitor_mentions']),
]
# pgvector HNSW index via raw SQL migration:
# CREATE INDEX ON conversations_conversation
#   USING hnsw (embedding vector_cosine_ops)
#   WITH (m = 16, ef_construction = 128);
```

---

## API Endpoints

### Auth

```
POST   /api/auth/register/              → Create account
POST   /api/auth/login/                 → JWT token pair (access + refresh)
POST   /api/auth/token/refresh/         → Refresh access token
GET    /api/auth/me/                    → Current user profile
```

### Customers

```
POST   /api/customers/                  → Create customer
GET    /api/customers/                  → List (search, pagination)
GET    /api/customers/{id}/             → Detail
PUT    /api/customers/{id}/             → Update
GET    /api/customers/{id}/timeline/    → All conversations for this customer
GET    /api/customers/search/?q=        → Autocomplete (name/email/company)
```

### Conversations

```
POST   /api/conversations/              → Create (text input, queues AI pipeline)
POST   /api/conversations/voice/        → Create from audio upload
GET    /api/conversations/              → List with filters
GET    /api/conversations/{id}/         → Detail + action items + attachments
PUT    /api/conversations/{id}/         → Update
DELETE /api/conversations/{id}/         → Soft delete
GET    /api/conversations/{id}/status/  → AI processing status (for polling)
```

### Action Items

```
GET    /api/action-items/               → List (filter: status, assignee, due_date, priority)
PUT    /api/action-items/{id}/          → Update status / assignee / due date
GET    /api/action-items/my/            → Assigned to current user
GET    /api/action-items/overdue/       → Past due date, not completed
```

### Search

```
GET    /api/search/?q=&mode=keyword|semantic|hybrid
       &customer=&date_from=&date_to=
       &sentiment=&type=&created_by=
       &topics=&has_pending_actions=
       &page=&page_size=

GET    /api/search/filters/             → Available facets with counts
```

### Analytics

```
GET    /api/analytics/volume/           → Conversation count over time
GET    /api/analytics/sentiment/        → Sentiment distribution + trends
GET    /api/analytics/team/             → Per-user activity stats
GET    /api/analytics/topics/           → Topic frequency ranking
GET    /api/analytics/competitors/      → Competitor mention frequency
GET    /api/analytics/follow-ups/       → Action item completion rates
GET    /api/analytics/summary/          → Dashboard overview (all key numbers)
```

---

## AI Processing Pipeline (Celery Tasks)

```
Conversation Created (text or audio)
        │
        ▼
┌─ Task: transcribe_audio ──────────────────────────┐
│  (skipped if no audio attachment)                  │
│  faster-whisper large-v3 → raw transcript          │
│  Save to attachment.transcription                  │
│  Merge into conversation.raw_text                  │
└───────────────────────┬────────────────────────────┘
                        ▼
┌─ Task: extract_with_llm ──────────────────────────┐
│  Send raw_text to Ollama (Llama 3.1 8B)            │
│  or OpenAI GPT-4o-mini as fallback                 │
│                                                    │
│  Prompt returns JSON:                              │
│    summary, requirements, pain_points,             │
│    pricing_discussion, next_steps,                 │
│    sentiment + score, action_items[],              │
│    topics[], competitor_mentions[]                  │
│                                                    │
│  Parse JSON → update Conversation fields           │
│  Create ActionItem records from extracted items     │
└───────────────────────┬────────────────────────────┘
                        ▼
┌─ Task: generate_embedding ────────────────────────┐
│  all-MiniLM-L6-v2 encodes raw_text                 │
│  Store 384-dim vector in conversation.embedding     │
└───────────────────────┬────────────────────────────┘
                        ▼
┌─ Task: index_in_elasticsearch ────────────────────┐
│  Index: raw_text, ai_summary, requirements,        │
│         pain_points, next_steps, topics             │
│  Document ID = conversation UUID                    │
└───────────────────────┬────────────────────────────┘
                        ▼
              ai_status = "completed"
```

Tasks are chained via Celery `chain()`. If any task fails, `ai_status` is set to `"failed"` and a retry is scheduled with exponential backoff (1min, 5min, 30min).

---

## React Pages + Key Components

### Page Map

| Page | Route | What It Does |
|---|---|---|
| Login | `/login` | Email + password → JWT → redirect to dashboard |
| Dashboard | `/` | Overview cards + recent activity feed |
| New Conversation | `/conversations/new` | Capture form: customer picker → type → text/voice → submit |
| Conversation Detail | `/conversations/:id` | Raw text, AI summary, extracted fields, action items, sentiment |
| Search | `/search` | Search bar + mode toggle + filters + paginated results |
| Customer Profile | `/customers/:id` | Customer info + conversation timeline + sentiment sparkline |
| Action Items | `/action-items` | Table view, filterable, inline status update |
| Analytics | `/analytics` | Charts: volume, sentiment, team activity, topics, follow-ups |
| Settings | `/settings` | Profile, team management (admin) |

### Key Component Behaviors

**CaptureForm.jsx**
- Customer autocomplete — calls `GET /api/customers/search/?q=` with 300ms debounce
- Conversation type dropdown + date picker
- Two tabs: Text Mode (structured fields + raw text) / Voice Mode (audio recorder)
- On submit → POST to API → redirect to detail page → poll `/status/` every 2s until AI completes
- Progress indicator: Transcribing → Analyzing → Summarizing → Done

**AudioRecorder.jsx**
- `navigator.mediaDevices.getUserMedia` for mic access
- Visual timer during recording
- Stop → Blob → upload as FormData with progress bar

**SearchPage.jsx**
- Single input with Keyword / Semantic / Hybrid toggle (hybrid default)
- 500ms debounce
- FilterSidebar: customer dropdown, date range, sentiment checkboxes, type, topics, "has pending actions"
- ResultCard: summary snippet with highlights, sentiment badge, customer, date, tags

**ConversationDetail.jsx**
- Left: raw text / transcript
- Right: AI summary card, requirements, pain points, pricing, next steps (collapsible)
- Sentiment badge + score, topic tags, competitor tags
- Action items with inline status toggle
- AI processing status if still running

**Analytics.jsx**
- Date range selector at top
- Grid of charts: VolumeChart (line/bar), SentimentTrend (area), TeamActivity (bar), TopicCloud (horizontal bar), FollowUpRate (donut)
- All powered by Recharts

---

## Implementation Phases

### Phase 1 — Django Backend (Weeks 1–4)

#### Week 1: Project Setup + Models

- [ ] Initialize Django project with the folder structure above
- [ ] Configure `settings/base.py`: database, installed apps, DRF, CORS, SimpleJWT
- [ ] Create Docker Compose: `django`, `postgres` (pgvector/pgvector:pg16), `redis`, `celery-worker`, `celery-beat`
- [ ] Create `Makefile`: `make up`, `make down`, `make migrate`, `make shell`, `make test`
- [ ] Write custom User model (UUID PK, email-based login)
- [ ] Write Customer model
- [ ] Write Conversation, ActionItem, Attachment models
- [ ] Run `makemigrations` + `migrate`
- [ ] Create pgvector HNSW index via raw SQL data migration
- [ ] Management command: `seed_demo_data` — creates test customers + conversations

**✓ Milestone:** `docker compose up` boots everything. DB tables created. Demo data loads.

#### Week 2: REST APIs

- [ ] Auth endpoints: register, login (SimpleJWT), refresh, me
- [ ] Customer CRUD + `/search/?q=` autocomplete (`icontains` on name, email, company)
- [ ] Conversation CRUD with filters via `django-filter` (customer, type, sentiment, date range, created_by, ai_status)
- [ ] Cursor-based pagination
- [ ] Detail endpoint nests action items + attachments
- [ ] Voice upload endpoint: multipart file → MinIO → Attachment record → queue pipeline
- [ ] Action Items: list, update, my-items, overdue
- [ ] API tests with `pytest` + DRF test client
- [ ] Swagger docs via `drf-spectacular` at `/api/docs/`

**✓ Milestone:** All CRUD endpoints working. Swagger docs live. Tests pass.

#### Week 3: AI Pipeline

- [ ] Add `faster-whisper` container (CPU for dev, GPU flag for prod)
- [ ] Add `ollama` container, auto-pull Llama 3.1 8B on boot
- [ ] `transcription_service.py`: file path → transcript text
- [ ] `ai_service.py`:
  - `extract_structured_data(raw_text)` → Ollama → parse JSON
  - Fallback to OpenAI GPT-4o-mini on timeout (>30s)
  - Retry on malformed JSON (up to 2 retries)
- [ ] `embedding_service.py`: load `all-MiniLM-L6-v2` once, `encode(text)` → numpy array
- [ ] Celery tasks in `tasks.py`: `transcribe_audio` → `extract_with_llm` → `generate_embedding` → `index_in_elasticsearch` (chained)
- [ ] Error handling: `ai_status = 'failed'`, log, schedule retry
- [ ] `/api/conversations/{id}/status/` polling endpoint

**✓ Milestone:** Text conversation → AI summary + action items in <30s. Audio → Whisper transcript → AI processing.

#### Week 4: Search

- [ ] Add Elasticsearch to Docker Compose
- [ ] ES index mapping with analyzers for conversation fields
- [ ] `search_service.py`:
  - `keyword_search(query, filters)` → ES BM25, field boosting (summary 2x), highlighting
  - `semantic_search(query, filters)` → embed query → pgvector cosine similarity
  - `hybrid_search(query, filters)` → both in parallel → Reciprocal Rank Fusion (k=60)
- [ ] Search endpoints: `GET /api/search/` + `GET /api/search/filters/`
- [ ] `index_in_elasticsearch` Celery task wired at end of AI pipeline
- [ ] Backfill command: `python manage.py reindex_elasticsearch`

**✓ Milestone:** Keyword, semantic, and hybrid search all returning relevant results.

---

### Phase 2 — React Frontend (Weeks 5–8)

#### Week 5: Setup + Auth + Layout + Dashboard

- [ ] Initialize Vite + React, install Tailwind + shadcn/ui
- [ ] `api/client.js`: Axios with JWT interceptor (auto-refresh on 401)
- [ ] Zustand `authStore.js`: login, logout, token state
- [ ] `Login.jsx`: email + password form → `/api/auth/login/` → store tokens → redirect
- [ ] `AppLayout.jsx`: collapsible sidebar + top header + user menu
- [ ] React Router: public (login) + protected routes
- [ ] `Dashboard.jsx`: cards from `/api/analytics/summary/` (conversation count, pending actions, avg sentiment) + recent 10 conversations list

**✓ Milestone:** Login works. Sidebar navigation. Dashboard shows live API data.

#### Week 6: Conversation Capture + Detail

- [ ] `CustomerSearch.jsx`: autocomplete with `useDebounce` (300ms)
- [ ] `AudioRecorder.jsx`: mic access, timer, Blob upload
- [ ] `CaptureForm.jsx`: customer select → type → text/voice tabs → submit
- [ ] `NewConversation.jsx` page
- [ ] `AIProcessingStatus.jsx`: polls status every 2s, animated step progress
- [ ] `SentimentBadge.jsx`: colored badge by sentiment level
- [ ] `ConversationDetail.jsx`: raw text, AI summary, extracted fields, action items, sentiment, processing status

**✓ Milestone:** Full flow: capture → AI processes → summary + action items visible.

#### Week 7: Search + Customer Profile

- [ ] `SearchModeToggle.jsx` + `SearchBar.jsx` + `FilterSidebar.jsx` + `ResultCard.jsx`
- [ ] `SearchPage.jsx`: bar + filters + paginated results
- [ ] `CustomerTimeline.jsx`: chronological conversation feed + sentiment sparkline (Recharts)
- [ ] `CustomerProfile.jsx`: customer header + timeline + stats

**✓ Milestone:** Search works across all modes with filters. Customer timeline view complete.

#### Week 8: Action Items + Analytics + Polish

- [ ] `ActionItems.jsx`: table with sort, filter by status/assignee/priority/overdue, inline status update
- [ ] Analytics components: `VolumeChart`, `SentimentTrend`, `TeamActivity`, `TopicCloud`, `FollowUpRate`
- [ ] `Analytics.jsx` page: chart grid with date range selector
- [ ] Responsive pass: tablet (1024px) + desktop
- [ ] Loading skeletons, error states with retry, empty states
- [ ] Toast notifications (react-hot-toast)

**✓ Milestone: Core platform complete — fully working end-to-end.**

---

### Phase 3 — Zoho CRM Integration (Weeks 9–10)

#### Week 9: Zoho Sync Service

- [ ] Create `zoho` Django app in backend
- [ ] Zoho OAuth2 token manager (refresh token in env, auto-refresh access token)
- [ ] **Zoho → Backend**: Celery periodic task syncs Contacts/Accounts/Deals into `customers_customer`
  - Bulk Read API for initial load
  - Incremental sync via `Modified_Time` filter
  - Populate `zoho_record_id` on matched Customer records
- [ ] **Backend → Zoho**: Celery task `sync_conversation_to_zoho`
  - Triggered after AI pipeline completes
  - Creates Note on linked Zoho record with formatted summary
  - Task `sync_action_item_to_zoho`: creates Task in Zoho CRM
- [ ] Add `zoho_sync_status` field to Conversation model (pending / synced / failed / not_applicable)
- [ ] Rate limiting: token bucket (100 req/min), exponential backoff on failure
- [ ] Dead-letter logging for permanently failed syncs

#### Week 10: Integration Testing + Deployment

- [ ] Zoho sync status badge on ConversationDetail page
- [ ] Sync health panel on Settings page
- [ ] Configure Zoho CRM custom module "Conversation Logs" in Zoho admin
- [ ] E2E test: capture → AI → summary in Zoho CRM Note + Task created
- [ ] `docker-compose.prod.yml`: gunicorn, nginx reverse proxy, SSL
- [ ] Deploy to staging server
- [ ] Load test: 50 concurrent submissions
- [ ] Security review: CORS, JWT config, file upload validation, SQL injection

**✓ Milestone: Full platform deployed with Zoho CRM sync.**

---

## Docker Compose Services

```yaml
services:
  django:
    build: ./backend
    command: python manage.py runserver 0.0.0.0:8000
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, redis, elasticsearch]
    volumes: ["./backend:/app"]

  celery-worker:
    build: ./backend
    command: celery -A config worker -l info -c 4
    env_file: .env
    depends_on: [django, redis]
    volumes: ["./backend:/app"]

  celery-beat:
    build: ./backend
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    env_file: .env
    depends_on: [redis]

  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: conv_intel
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes: [postgres_data:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  elasticsearch:
    image: elasticsearch:8.13.0
    ports: ["9200:9200"]
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes: [es_data:/usr/share/elasticsearch/data]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes: [minio_data:/data]

  ollama:
    image: ollama/ollama
    ports: ["11434:11434"]
    volumes: [ollama_data:/root/.ollama]

  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    volumes: ["./frontend/src:/app/src"]

volumes:
  postgres_data:
  es_data:
  minio_data:
  ollama_data:
```

---

## Key Dependencies

### Backend — `requirements/base.txt`

```
django>=5.0
djangorestframework>=3.15
djangorestframework-simplejwt>=5.3
django-filter>=24.0
django-cors-headers>=4.3
django-celery-beat>=2.6
drf-spectacular>=0.27
celery>=5.4
redis>=5.0
psycopg[binary]>=3.1
pgvector>=0.3
django-storages>=1.14
boto3>=1.34
elasticsearch>=8.13
sentence-transformers>=3.0
faster-whisper>=1.0
httpx>=0.27
openai>=1.30
structlog>=24.1
gunicorn>=22.0
```

### Frontend — `package.json`

```json
{
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "react-router-dom": "^6.23",
    "axios": "^1.7",
    "zustand": "^4.5",
    "@tanstack/react-query": "^5.40",
    "recharts": "^2.12",
    "tailwindcss": "^3.4",
    "clsx": "^2.1",
    "tailwind-merge": "^2.3",
    "lucide-react": "^0.383",
    "react-hot-toast": "^2.4",
    "date-fns": "^3.6"
  }
}
```

---

## Week-by-Week Summary

| Week | Focus | Milestone |
|---|---|---|
| **1** | Django project + Docker Compose + models + migrations | `docker compose up` runs, DB ready |
| **2** | Auth + Customer CRUD + Conversation CRUD + Action Items | All endpoints working, Swagger live |
| **3** | Whisper + Ollama + LLM extraction + embeddings pipeline | AI processes conversations end-to-end |
| **4** | Elasticsearch + keyword/semantic/hybrid search | Three search modes returning results |
| **5** | React setup + auth + layout + dashboard | Login works, dashboard shows live data |
| **6** | Capture form + audio recorder + detail page | Full capture → AI → detail flow in UI |
| **7** | Search page + filters + customer profile + timeline | Search and customer views complete |
| **8** | Action items + analytics charts + polish | **Core platform complete** |
| **9** | Zoho OAuth + bidirectional sync service | Conversations sync to Zoho Notes/Tasks |
| **10** | Zoho UI + E2E testing + staging deploy | **Full platform deployed** |