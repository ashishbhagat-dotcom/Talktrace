# Lead/Account Creation via AI Conversation — Implementation Plan

End-to-end flow: user picks Lead or Account → records/types/uploads a conversation → AI extracts CRM fields → user reviews & edits → record is created in Zoho with the conversation attached as a note.

Mark each item with `[x]` as it is completed.

---

## Phase 1 — Backend Foundation

### 1.1 Data model
- [x] Create `CRMDraft` model in `apps/integrations/models.py` with fields:
  - `id` (UUID), `created_by` (FK User), `record_type` (`lead` | `account`)
  - `raw_text` (text), `attachment` (FK Attachment, nullable — for audio)
  - `extracted_fields` (JSONField), `ai_summary` (text)
  - `action_items` (JSONField), `topics` (JSONField), `confidence` (JSONField)
  - `status` (`pending` | `extracting` | `ready` | `submitted` | `failed`)
  - `zoho_record_id`, `zoho_note_id`, `error_message`
  - `edit_log` (JSONField — list of `{field, old, new, at}` for audit)
  - `created_at`, `updated_at`, `submitted_at`
- [x] Add `field_schema_cache` + `field_schema_fetched_at` to `ZohoCredential`
- [x] Generate and apply migration (`0003_zohocredential_field_schema_cache_and_more`)

### 1.2 Field schema (dynamic fetch + cache) — layout-aware

**Known from live Zoho fetch (`2026-06-15`, sandbox, E2E Networks org):**

**Leads — Standard Layout requires 4 fields:**
- `First_Name` (text, max 40)
- `Last_Name` (text, max 80) — also system_mandatory
- `Email` (email, max 100)
- `Lead_Status` (picklist) — values: Junk Lead, Cold, Customer Validation Pending, Do Not Disturb, Duplicate Lead, Existing Customer, Focused Lead, Not Qualified, From Trial to Cold/Hot/Warm, Hot, Meeting Setup Requested, Prospecting, Warm, Won, Dead, Pre-Qualified, E2E Startup Program Credits

**Accounts — Standard Layout requires 11 fields:**
- `Account_Name` (text, max 200) — also system_mandatory
- `Account_Type` (picklist): Distributor, Integrator, Public + Private Cloud Customer, Investor, Reseller, Billing Partner, Old Lost Customer
- `Revenue_Range_Monthly` (picklist): More than 50K, 20K to 50K, Below 20K
- `Priority_Account` (picklist): Low, Medium, High, Very High
- `Revenue_at_Risk` (picklist): None, Low, Medium, High, Very High
- `Customer_Type` (picklist, labeled "Account Status"): Un-Managed Cloud Customer, Old Customer/ Lost Customer, CloudOps customer
- `Email_ID` (text, max 255, labeled "Registered Email ID")
- `CRN` (text, max 255)
- `Opportunity_1` (picklist, 15 E2E products): AI Lab As A Service, Sovereign Cloud, Cpanel Series, CPU Intensive Computing series, Disk Intensive Series, GPU Series, HPC series, Kubernetes, Memory Intensive Computing Series, Plesk Series, Private Cloud, SDS Series, Second Generation Memory Intensive, Webuzo series, Windows series
- `LinkedIn_URL` (text, max 255)
- `Business` (picklist, 26 industry options)

**Tasks:**
- [x] Add `field_schema_cache` + `field_schema_fetched_at` to `ZohoCredential`
- [x] Create `apps/integrations/services/zoho_fields.py` with:
  - `fetch_schema_for_module(token, module)` — fetches layouts + fields; returns dict keyed by api_name
  - `get_schema(credential, module, force_refresh=False)` — 24h-cached
  - `required_fields(schema)`, `extraction_fields(record_type)`, `module_for_record_type(record_type)`
  - `EXTRACTION_FIELDS_LEAD` and `EXTRACTION_FIELDS_ACCOUNT` constants

### 1.3 AI extraction service
- [x] Created `apps/integrations/services/crm_extraction.py` with:
  - `extract_crm_fields(raw_text, record_type, schema)` — schema-driven prompt
  - Dynamic prompt embeds picklist options so LLM picks valid values
  - Per-field type coercion + length truncation + picklist validation
  - Returns `{fields, summary, action_items, topics, confidence}`
  - Verified on sample Lead conversation: correctly extracted name/email/phone/company/designation/Lead_Source picklist

### 1.4 Celery extraction task
- [x] Added `extract_crm_draft(draft_id)` in `apps/integrations/tasks.py`
  - Handles audio (transcribes first) and text drafts
  - Sets status → `extracting` → `ready` (or `failed` with error_message)
  - Verified end-to-end with a Lead sample: 6 fields extracted in ~40s

### 1.5 Zoho client extensions
- [x] Added `create_record(access_token, module, fields)` to `zoho_client.py`
- Existing `create_note` reused for attaching transcript

### 1.6 Submit-to-Zoho service
- [x] Added `submit_draft_to_zoho(draft, credential)` to `zoho_sync.py`
  - Defense-in-depth: re-validates required fields before calling Zoho
  - Creates record → attaches note (summary + topics + action items + transcript)
  - Mirrors as local `Customer` so it shows in dashboards
  - Updates draft.status to `submitted` + sets `zoho_record_id`, `zoho_note_id`, `submitted_at`
- [x] Added `submit_crm_draft(draft_id)` Celery task wrapper

---

## Phase 2 — Backend API

### 2.1 Serializers
- [x] `CRMDraftCreateSerializer` — record_type + raw_text/attachment_id with validation
- [x] `CRMDraftSerializer` — full draft + live schema + required + extraction_field_order + missing_required
- [x] `CRMDraftUpdateSerializer` — patches extracted_fields and appends to edit_log

### 2.2 Views
- [x] `GET /api/crm-drafts/` — list (own drafts, or all if admin)
- [x] `POST /api/crm-drafts/` — create draft + kick off `extract_crm_draft.delay(...)`
- [x] `GET /api/crm-drafts/<id>/` — full draft with schema
- [x] `PATCH /api/crm-drafts/<id>/` — update fields, append edit_log
- [x] `DELETE /api/crm-drafts/<id>/` — discard a draft
- [x] `POST /api/crm-drafts/<id>/submit/` — validate required, create Zoho Lead/Account, attach note, mirror as local Customer

### 2.3 URL wiring
- [x] Routes added to `apps/integrations/urls.py`

### 2.4 Permissions / scope
- [x] Auth required; non-admin users see only their own drafts; admin sees all
- [x] Submitted drafts cannot be edited

### 2.5 End-to-end verification
- [x] Real Lead created in Zoho sandbox: record_id `7342969000306027005`, note_id `7342969000306027008`

---

## Phase 3 — Frontend

### 3.1 API layer
- [x] Added `listCrmDrafts`, `createCrmDraft`, `getCrmDraft`, `updateCrmDraft`, `deleteCrmDraft`, `submitCrmDraft` to `frontend/src/api/integrations.js`

### 3.2 Create-from-Conversation wizard
- [x] Route `/create-record` → `pages/CreateRecord.jsx`
- [x] Step A: Lead / Account picker (two cards)
- [x] Step B: Three input modes — Type / Record (AudioRecorder) / Upload (text or audio file)
- [x] Multipart support added to backend `POST /api/crm-drafts/` for audio uploads (made `Attachment.conversation` nullable + migration 0004)

### 3.3 Draft review screen
- [x] `components/crm-drafts/DraftReview.jsx`:
  - Polls every 2s while status is `pending`/`extracting`, shows analyzing spinner
  - Renders one input per field using `extraction_field_order` + `schema` from API
  - Picklist → `<select>` with org's actual values; textarea/email/phone/url/number resolved from `data_type`
  - Required fields get red border + "Required" label + amber banner listing all missing
  - AI badge on every field the LLM filled (via `confidence` map)
  - Debounced auto-save (600ms) → `updateCrmDraft` so `edit_log` stays current
  - Side panel: AI summary, action items, topics, expandable original transcript

### 3.4 Submit & success
- [x] Submit flushes pending edits then calls `submitCrmDraft(id)`
- [x] Success screen shows Zoho record ID + "Create another" / "Back to Dashboard"
- [x] Failures surface server `missing_required` array as a toast

### 3.5 Navigation
- [x] Sidebar nav entry "Create Lead/Account" with Sparkles icon

---

## Phase 4 — Polish & QA

### 4.1 Validation & UX
- [ ] Frontend blocks submit until all required fields filled
- [ ] Backend re-validates required fields on submit (defense in depth)
- [ ] Email/phone format hints (non-blocking)

### 4.2 Audit
- [ ] Verify `edit_log` captures every user change with `field`, `old`, `new`, `at`
- [ ] Verify original transcript + AI summary survive on the draft even after submit

### 4.3 End-to-end test on server
- [ ] Lead flow: type a conversation → extract → review → submit → confirm Lead + Note created in Zoho
- [ ] Account flow: same with Account
- [ ] Audio flow: record audio → confirm transcription runs before extraction
- [ ] Missing-field flow: short conversation with only a name → confirm `Last_Name` (Lead) / `Account_Name` (Account) is flagged as missing
- [ ] Token fallback: rep without Zoho connection → confirm submit succeeds via admin fallback

### 4.4 Documentation
- [ ] Update `DEPLOYMENT.md` if any new env var introduced (none expected)
- [ ] Add a short section to README on the new flow

---

## Open Decisions (resolve as we go)

- **Required-field source**: ~~hardcoded~~ → **dynamic fetch with 24h cache**. Live Zoho fetch confirms only `Last_Name` (Leads) / `Account_Name` (Accounts) are mandatory in this org, but picklists (Lead_Source, Industry, Salutation, Account_Type, Ownership) carry org-specific values that we must respect.
- **Duplicate detection**: skipped for MVP. Could later check `Email` against existing Zoho records before create.
- **Confidence scoring UX**: store per-field confidence from LLM; surface only the badge initially. Could later sort/filter low-confidence fields.

---

## Out of Scope (for now)

- Editing custom Zoho fields per org (would need dynamic schema fetch)
- Bulk-creating multiple records from one conversation
- Re-running extraction with a different model after the draft is already created
