import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { CheckCircle2, ChevronLeft, Loader2, Sparkles, AlertCircle, ExternalLink } from "lucide-react";
import toast from "react-hot-toast";
import { getCrmDraft, updateCrmDraft, submitCrmDraft } from "../../api/integrations";
import Select from "../ui/Select";

export default function DraftReview({ draftId, onBack, onDone }) {
  const [fields, setFields] = useState(null);     // local editable copy
  const [submitted, setSubmitted] = useState(null); // server response after submit
  const debounceRef = useRef(null);
  const lastSavedRef = useRef({});

  const { data: draft, isLoading } = useQuery({
    queryKey: ["crm-draft", draftId],
    queryFn: () => getCrmDraft(draftId).then((r) => r.data),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "pending" || s === "extracting" ? 2000 : false;
    },
  });

  // Hydrate local field state once extraction completes
  useEffect(() => {
    if (draft && fields === null && draft.status === "ready") {
      setFields({ ...(draft.extracted_fields || {}) });
      lastSavedRef.current = { ...(draft.extracted_fields || {}) };
    }
  }, [draft, fields]);

  const patchMutation = useMutation({
    mutationFn: (patch) => updateCrmDraft(draftId, { extracted_fields: patch }),
  });

  // Debounced save when user edits a field
  const saveSoon = (next) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const patch = {};
      for (const k of Object.keys(next)) {
        if (next[k] !== lastSavedRef.current[k]) patch[k] = next[k] || null;
      }
      for (const k of Object.keys(lastSavedRef.current)) {
        if (!(k in next)) patch[k] = null;
      }
      if (Object.keys(patch).length === 0) return;
      patchMutation.mutate(patch, {
        onSuccess: (r) => {
          lastSavedRef.current = { ...(r.data.extracted_fields || {}) };
        },
      });
    }, 600);
  };

  const setField = (api, value) => {
    setFields((prev) => {
      const next = { ...prev, [api]: value };
      saveSoon(next);
      return next;
    });
  };

  const submitMutation = useMutation({
    mutationFn: async () => {
      // Flush any pending edits first
      if (debounceRef.current) clearTimeout(debounceRef.current);
      const patch = {};
      for (const k of Object.keys(fields || {})) {
        if (fields[k] !== lastSavedRef.current[k]) patch[k] = fields[k] || null;
      }
      if (Object.keys(patch).length > 0) {
        await updateCrmDraft(draftId, { extracted_fields: patch });
      }
      const r = await submitCrmDraft(draftId);
      return r.data;
    },
    onSuccess: (d) => {
      setSubmitted(d);
      toast.success(`${d.record_type === "lead" ? "Lead" : "Account"} created in Zoho!`);
    },
    onError: (err) => {
      const data = err.response?.data || {};
      const msg = data.error || "Submit failed";
      if (data.missing_required?.length) {
        toast.error(`Missing required: ${data.missing_required.join(", ")}`);
      } else {
        toast.error(msg);
      }
    },
  });

  if (isLoading || !draft) {
    return <div className="text-slate-500 text-sm">Loading draft…</div>;
  }

  if (submitted) {
    return <SuccessScreen draft={submitted} onDone={onDone} />;
  }

  if (draft.status === "pending" || draft.status === "extracting") {
    return <ExtractingScreen draft={draft} />;
  }

  if (draft.status === "failed") {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <button onClick={onBack} className="text-sm text-slate-500 hover:text-slate-800 flex items-center gap-1">
          <ChevronLeft size={16} /> Back
        </button>
        <div className="card p-6">
          <div className="flex items-start gap-3">
            <AlertCircle size={20} className="text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-slate-800">Extraction failed</h3>
              <p className="text-sm text-slate-600 mt-1">{draft.error_message || "Something went wrong."}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // status === "ready"
  return (
    <ReviewForm
      draft={draft}
      fields={fields || {}}
      setField={setField}
      onBack={onBack}
      onSubmit={() => submitMutation.mutate()}
      submitting={submitMutation.isPending}
      patchSaving={patchMutation.isPending}
    />
  );
}

function ExtractingScreen({ draft }) {
  return (
    <div className="max-w-3xl mx-auto">
      <div className="card p-8 text-center">
        <Sparkles size={28} className="text-brand-500 mx-auto mb-3 animate-pulse" />
        <h3 className="font-semibold text-slate-800">Analyzing conversation…</h3>
        <p className="text-sm text-slate-500 mt-1">
          {draft.attachment ? "Transcribing audio then extracting CRM fields." : "Extracting CRM fields with AI."}
        </p>
        <Loader2 size={18} className="animate-spin text-slate-400 mx-auto mt-4" />
      </div>
    </div>
  );
}

function ReviewForm({ draft, fields, setField, onBack, onSubmit, submitting, patchSaving }) {
  const order = draft.extraction_field_order || [];
  const schema = draft.schema || {};
  const requiredSet = useMemo(() => new Set(draft.required || []), [draft.required]);
  const confidence = draft.confidence || {};

  const missing = (draft.required || []).filter((api) => !fields[api]);
  const canSubmit = missing.length === 0 && !submitting;

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <button onClick={onBack} className="text-sm text-slate-500 hover:text-slate-800 flex items-center gap-1">
        <ChevronLeft size={16} /> Back
      </button>

      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-bold text-slate-800">
          Review {draft.record_type === "lead" ? "Lead" : "Account"} details
        </h1>
        <span className="text-xs text-slate-400">
          {patchSaving ? "Saving…" : "All changes saved"}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Form */}
        <div className="lg:col-span-2 card p-6 space-y-4">
          {missing.length > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-2.5 text-sm text-yellow-800">
              <strong>{missing.length} required field{missing.length === 1 ? "" : "s"} missing:</strong>{" "}
              {missing.map((m) => schema[m]?.label || m).join(", ")}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {order.map((api) => (
              <FieldInput
                key={api}
                api={api}
                spec={schema[api]}
                value={fields[api]}
                onChange={(v) => setField(api, v)}
                required={requiredSet.has(api)}
                confidence={confidence[api]}
              />
            ))}
          </div>

          <div className="border-t border-slate-100 pt-4 flex justify-between items-center">
            <span className="text-xs text-slate-400">
              {missing.length === 0 ? "Ready to create in Zoho" : `Fill ${missing.length} more required field${missing.length === 1 ? "" : "s"}`}
            </span>
            <button
              onClick={onSubmit}
              disabled={!canSubmit}
              className="btn-primary flex items-center gap-2"
            >
              {submitting && <Loader2 size={15} className="animate-spin" />}
              Create {draft.record_type === "lead" ? "Lead" : "Account"}
            </button>
          </div>
        </div>

        {/* Side panel: summary + transcript */}
        <div className="space-y-3">
          {draft.ai_summary && (
            <div className="card p-4">
              <h3 className="text-sm font-semibold text-slate-800 mb-2 flex items-center gap-1.5">
                <Sparkles size={14} className="text-brand-500" /> AI Summary
              </h3>
              <p className="text-sm text-slate-600 leading-relaxed">{draft.ai_summary}</p>
            </div>
          )}

          {draft.action_items?.length > 0 && (
            <div className="card p-4">
              <h3 className="text-sm font-semibold text-slate-800 mb-2">Action Items</h3>
              <ul className="space-y-1.5">
                {draft.action_items.map((item, i) => {
                  const desc = typeof item === "string" ? item : item.description;
                  const due = typeof item === "object" ? item.due_date : null;
                  return (
                    <li key={i} className="text-sm text-slate-600">
                      • {desc}
                      {due && <span className="text-slate-400 text-xs ml-1">(due {due})</span>}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {draft.topics?.length > 0 && (
            <div className="card p-4">
              <h3 className="text-sm font-semibold text-slate-800 mb-2">Topics</h3>
              <div className="flex flex-wrap gap-1.5">
                {draft.topics.map((t) => (
                  <span key={t} className="badge bg-blue-100 text-blue-700">{t}</span>
                ))}
              </div>
            </div>
          )}

          {draft.raw_text && (
            <details className="card p-4">
              <summary className="text-sm font-semibold text-slate-800 cursor-pointer">
                Original Conversation
              </summary>
              <pre className="text-xs text-slate-600 mt-2 whitespace-pre-wrap font-mono">{draft.raw_text}</pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}

function FieldInput({ api, spec, value, onChange, required, confidence }) {
  if (!spec) return null;
  const label = spec.label || api;
  const isMissing = required && !value;
  const aiFilled = confidence != null && value != null;

  const baseInput =
    "input " + (isMissing ? "border-red-300 focus:border-red-500" : "");

  return (
    <div>
      <label className="label flex items-center gap-1">
        {label}
        {required && <span className="text-red-500">*</span>}
        {aiFilled && (
          <span className="ml-auto inline-flex items-center gap-0.5 text-[10px] uppercase tracking-wide text-brand-600 font-medium">
            <Sparkles size={9} /> AI
          </span>
        )}
      </label>

      {spec.data_type === "picklist" ? (
        <Select
          value={value || ""}
          onChange={(v) => onChange(v || null)}
          options={(spec.picklist_values || []).map((v) => ({ value: v, label: v }))}
          placeholder="— Select —"
          allowClear={!required}
          invalid={isMissing}
        />
      ) : spec.data_type === "textarea" ? (
        <textarea
          value={value || ""}
          onChange={(e) => onChange(e.target.value || null)}
          rows={3}
          maxLength={spec.max_length || undefined}
          className={baseInput}
        />
      ) : spec.data_type === "boolean" ? (
        <input
          type="checkbox"
          checked={!!value}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4"
        />
      ) : (
        <input
          type={spec.data_type === "email" ? "email" : spec.data_type === "phone" ? "tel" : spec.data_type === "website" ? "url" : spec.data_type === "integer" || spec.data_type === "bigint" || spec.data_type === "double" || spec.data_type === "currency" ? "number" : "text"}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
          maxLength={spec.max_length || undefined}
          className={baseInput}
        />
      )}

      {isMissing && <p className="text-xs text-red-600 mt-1">Required</p>}
    </div>
  );
}

function SuccessScreen({ draft, onDone }) {
  const label = draft.record_type === "lead" ? "Lead" : "Account";
  return (
    <div className="max-w-2xl mx-auto">
      <div className="card p-8 text-center">
        <CheckCircle2 size={40} className="text-green-500 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-slate-800">{label} created in Zoho!</h2>
        <p className="text-sm text-slate-500 mt-1">
          The conversation has been saved as a note on the new record.
        </p>
        {draft.zoho_record_id && (
          <div className="mt-4 bg-slate-50 rounded-lg px-4 py-2 text-sm font-mono text-slate-700 inline-block">
            Zoho ID: {draft.zoho_record_id}
          </div>
        )}
        <div className="flex justify-center gap-2 mt-6">
          <button onClick={onDone} className="btn-secondary">
            Back to Dashboard
          </button>
          <button onClick={() => window.location.reload()} className="btn-primary flex items-center gap-2">
            Create another
          </button>
        </div>
      </div>
    </div>
  );
}
