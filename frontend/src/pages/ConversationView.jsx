import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, CheckCircle, Clock, AlertCircle, Sparkles, Loader2 } from "lucide-react";
import { getConversation, analyzeConversation, confirmConversation } from "../api/conversations";
import { updateActionItem } from "../api/actionItems";
import SentimentBadge from "../components/conversations/SentimentBadge";
import AIProcessingStatus from "../components/conversations/AIProcessingStatus";
import Select from "../components/ui/Select";
import { formatDate, formatDateTime, conversationTypeLabel } from "../utils/formatters";
import toast from "react-hot-toast";

const STATUS_OPTIONS = [
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In Progress" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

function CollapsibleSection({ title, content }) {
  const [open, setOpen] = useState(true);
  if (!content) return null;
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-sm font-medium text-slate-700"
      >
        {title}
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>
      {open && <div className="px-4 py-3 text-sm text-slate-700 whitespace-pre-wrap">{content}</div>}
    </div>
  );
}

const STATUS_STYLES = {
  pending: "bg-yellow-100 text-yellow-700",
  in_progress: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-slate-100 text-slate-500",
};

export default function ConversationView() {
  const { id } = useParams();
  const queryClient = useQueryClient();

  const { data: conversation, isLoading } = useQuery({
    queryKey: ["conversation", id],
    queryFn: () => getConversation(id).then((r) => r.data),
    refetchInterval: (query) => {
      const s = query.state.data?.ai_status;
      // Poll while the AI pipeline is actively working. Stop polling when
      // waiting on the user (transcribed / ready_for_review) or done.
      return s === "pending" || s === "transcribing" || s === "processing" ? 3000 : false;
    },
  });

  const updateStatus = useMutation({
    mutationFn: ({ itemId, status }) => updateActionItem(itemId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries(["conversation", id]);
      toast.success("Action item updated");
    },
  });

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 bg-slate-200 animate-pulse rounded-xl" />
        ))}
      </div>
    );
  }

  if (!conversation) return <div className="text-slate-500">Conversation not found</div>;

  const aiDone = conversation.ai_status === "completed";
  const transcriptReviewMode = conversation.ai_status === "transcribed";
  const aiReviewMode = conversation.ai_status === "ready_for_review";

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-slate-500 mb-1">
            <Link to="/" className="hover:text-brand-600">Dashboard</Link>
            <span>/</span>
            <span>Conversation</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-800">
            {conversationTypeLabel(conversation.conversation_type)} with{" "}
            <Link to={`/customers/${conversation.customer?.id}`} className="text-brand-600 hover:underline">
              {conversation.customer?.name}
            </Link>
          </h1>
          <p className="text-slate-500 mt-1">{formatDateTime(conversation.interaction_date)}</p>
        </div>
        {aiDone && <SentimentBadge sentiment={conversation.sentiment} score={conversation.sentiment_score} />}
      </div>

      {/* Transcript review (after audio transcription, before AI extraction) */}
      {transcriptReviewMode && (
        <TranscriptReview conversation={conversation} />
      )}

      {/* AI insights review (after extraction, before push to CRM) */}
      {aiReviewMode && (
        <AIInsightsReview conversation={conversation} />
      )}

      {/* AI Processing spinner — shown only while AI is actively working */}
      {!transcriptReviewMode && !aiReviewMode && !aiDone && conversation.ai_status !== "failed" && (
        <AIProcessingStatus
          conversationId={id}
          hasAudio={conversation.attachments?.length > 0}
        />
      )}

      {/* Main content grid — hidden during transcript / AI review */}
      {!transcriptReviewMode && !aiReviewMode && (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Raw text */}
        <div className="card p-6">
          <h2 className="font-semibold text-slate-800 mb-3">
            {conversation.attachments?.length > 0 ? "Transcript" : "Conversation Notes"}
          </h2>
          <div className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed max-h-[500px] overflow-y-auto font-mono bg-slate-50 rounded-lg p-4">
            {conversation.raw_text || "No content yet..."}
          </div>
        </div>

        {/* Right: AI insights */}
        <div className="space-y-3">
          {aiDone ? (
            <>
              {conversation.ai_summary ? (
                <div className="card p-5">
                  <h2 className="font-semibold text-slate-800 mb-2">AI Summary</h2>
                  <p className="text-sm text-slate-700 leading-relaxed">{conversation.ai_summary}</p>
                </div>
              ) : (
                <div className="card p-5 border-dashed">
                  <h2 className="font-semibold text-slate-500 mb-1 text-sm">AI Summary</h2>
                  <p className="text-xs text-slate-400">No summary extracted — the transcript may be too short or unclear.</p>
                </div>
              )}
              <CollapsibleSection title="Customer Requirements" content={conversation.customer_requirements} />
              <CollapsibleSection title="Pain Points" content={conversation.pain_points} />
              <CollapsibleSection title="Pricing Discussion" content={conversation.pricing_discussion} />
              <CollapsibleSection title="Next Steps" content={conversation.next_steps} />

              {/* Tags */}
              {(conversation.topics?.length > 0 || conversation.competitor_mentions?.length > 0) ? (
                <div className="card p-4 space-y-3">
                  {conversation.topics?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-slate-500 mb-2">Topics</p>
                      <div className="flex flex-wrap gap-1.5">
                        {conversation.topics.map((t) => (
                          <span key={t} className="badge bg-blue-100 text-blue-700">{t}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {conversation.competitor_mentions?.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-slate-500 mb-2">Competitors Mentioned</p>
                      <div className="flex flex-wrap gap-1.5">
                        {conversation.competitor_mentions.map((c) => (
                          <span key={c} className="badge bg-red-100 text-red-700">{c}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : conversation.ai_summary ? null : (
                <div className="card p-4 border-dashed text-center">
                  <p className="text-xs text-slate-400">No topics or competitors extracted.</p>
                </div>
              )}
            </>
          ) : (
            <div className="card p-6 text-center text-slate-400">
              <p className="text-sm">AI insights will appear here once processing completes.</p>
            </div>
          )}
        </div>
      </div>
      )}

      {/* Action Items */}
      {!transcriptReviewMode && !aiReviewMode && conversation.action_items?.length > 0 && (
        <div className="card">
          <div className="px-6 py-4 border-b border-slate-100">
            <h2 className="font-semibold text-slate-800">
              Action Items ({conversation.action_items.length})
            </h2>
          </div>
          <div className="divide-y divide-slate-100">
            {conversation.action_items.map((item) => (
              <div key={item.id} className="flex items-center justify-between px-6 py-4 gap-4">
                <div className="flex items-start gap-3 min-w-0">
                  {item.status === "completed" ? (
                    <CheckCircle size={18} className="text-green-500 mt-0.5 flex-shrink-0" />
                  ) : item.due_date && new Date(item.due_date) < new Date() ? (
                    <AlertCircle size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                  ) : (
                    <Clock size={18} className="text-slate-400 mt-0.5 flex-shrink-0" />
                  )}
                  <div className="min-w-0">
                    <p className={`text-sm text-slate-800 ${item.status === "completed" ? "line-through text-slate-400" : ""}`}>
                      {item.description}
                    </p>
                    {item.due_date && (
                      <p className="text-xs text-slate-500 mt-0.5">Due {formatDate(item.due_date)}</p>
                    )}
                  </div>
                </div>
                <div className="flex-shrink-0">
                  <Select
                    size="sm"
                    value={item.status}
                    onChange={(v) => updateStatus.mutate({ itemId: item.id, status: v })}
                    options={STATUS_OPTIONS}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TranscriptReview({ conversation }) {
  const queryClient = useQueryClient();
  const [transcript, setTranscript] = useState(conversation.raw_text || "");

  // Sync editor when conversation data refreshes (e.g., transcript just arrived)
  useEffect(() => {
    setTranscript(conversation.raw_text || "");
  }, [conversation.id, conversation.raw_text]);

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeConversation(conversation.id, transcript),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", conversation.id] });
      toast.success("AI analysis started");
    },
    onError: (err) => {
      toast.error(err.response?.data?.error || "Couldn't start analysis");
    },
  });

  const wordCount = transcript.trim().split(/\s+/).filter(Boolean).length;
  const empty = transcript.trim().length === 0;

  return (
    <div className="card p-6 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-slate-800 flex items-center gap-2">
            Review transcript
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Whisper transcribed your audio. Fix any misheard names, emails, or numbers — better transcript means better AI extraction.
          </p>
        </div>
        <span className="text-xs text-slate-400 shrink-0 mt-1">
          {wordCount} words · {transcript.length} chars
        </span>
      </div>

      <textarea
        value={transcript}
        onChange={(e) => setTranscript(e.target.value)}
        rows={14}
        className="input font-mono text-sm leading-relaxed"
        placeholder="Empty transcript — Whisper couldn't extract any text from the audio."
      />

      <div className="flex justify-between items-center pt-2 border-t border-slate-100">
        <span className="text-xs text-slate-400">
          {empty ? "Add some text to enable analysis" : "Ready to extract insights"}
        </span>
        <button
          onClick={() => analyzeMutation.mutate()}
          disabled={analyzeMutation.isPending || empty}
          className="btn-primary flex items-center gap-2"
        >
          {analyzeMutation.isPending ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <Sparkles size={15} />
          )}
          Analyze with AI
        </button>
      </div>
    </div>
  );
}

const SENTIMENT_OPTIONS = [
  { value: "very_negative", label: "Very Negative" },
  { value: "negative", label: "Negative" },
  { value: "neutral", label: "Neutral" },
  { value: "positive", label: "Positive" },
  { value: "very_positive", label: "Very Positive" },
];

const PRIORITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

function AIInsightsReview({ conversation }) {
  const queryClient = useQueryClient();
  const [edits, setEdits] = useState({
    ai_summary: conversation.ai_summary || "",
    customer_requirements: conversation.customer_requirements || "",
    pain_points: conversation.pain_points || "",
    pricing_discussion: conversation.pricing_discussion || "",
    next_steps: conversation.next_steps || "",
    sentiment: conversation.sentiment || "neutral",
    topics: conversation.topics || [],
    competitor_mentions: conversation.competitor_mentions || [],
  });
  const [actionItems, setActionItems] = useState(
    (conversation.action_items || []).map((a) => ({
      id: a.id,
      description: a.description || "",
      due_date: a.due_date || "",
      priority: a.priority || "medium",
      status: a.status || "pending",
    }))
  );

  // Re-hydrate if the underlying conversation refreshes
  useEffect(() => {
    setEdits({
      ai_summary: conversation.ai_summary || "",
      customer_requirements: conversation.customer_requirements || "",
      pain_points: conversation.pain_points || "",
      pricing_discussion: conversation.pricing_discussion || "",
      next_steps: conversation.next_steps || "",
      sentiment: conversation.sentiment || "neutral",
      topics: conversation.topics || [],
      competitor_mentions: conversation.competitor_mentions || [],
    });
    setActionItems(
      (conversation.action_items || []).map((a) => ({
        id: a.id,
        description: a.description || "",
        due_date: a.due_date || "",
        priority: a.priority || "medium",
        status: a.status || "pending",
      }))
    );
  }, [conversation.id]);

  const setField = (k, v) => setEdits((e) => ({ ...e, [k]: v }));

  const updateItem = (idx, patch) =>
    setActionItems((items) => items.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  const removeItem = (idx) =>
    setActionItems((items) => items.filter((_, i) => i !== idx));
  const addItem = () =>
    setActionItems((items) => [...items, { description: "", due_date: "", priority: "medium", status: "pending" }]);

  const confirmMutation = useMutation({
    mutationFn: () =>
      confirmConversation(conversation.id, {
        ...edits,
        action_items: actionItems
          .filter((a) => a.description.trim())
          .map((a) => ({
            id: a.id,
            description: a.description,
            due_date: a.due_date || null,
            priority: a.priority,
            status: a.status,
          })),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", conversation.id] });
      toast.success("Pushed to Zoho CRM!");
    },
    onError: (err) => {
      toast.error(err.response?.data?.error || "Couldn't confirm");
    },
  });

  return (
    <div className="card p-6 space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-slate-800 flex items-center gap-2">
            <Sparkles size={16} className="text-brand-500" /> Review AI insights
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Edit anything the AI got wrong. Nothing is pushed to Zoho until you confirm.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <ReviewField label="AI Summary" rows={4} value={edits.ai_summary}
            onChange={(v) => setField("ai_summary", v)} />
          <ReviewField label="Customer Requirements" rows={3} value={edits.customer_requirements}
            onChange={(v) => setField("customer_requirements", v)} />
          <ReviewField label="Pain Points" rows={3} value={edits.pain_points}
            onChange={(v) => setField("pain_points", v)} />
        </div>
        <div className="space-y-4">
          <ReviewField label="Pricing Discussion" rows={3} value={edits.pricing_discussion}
            onChange={(v) => setField("pricing_discussion", v)} />
          <ReviewField label="Next Steps" rows={3} value={edits.next_steps}
            onChange={(v) => setField("next_steps", v)} />
          <div>
            <label className="label">Sentiment</label>
            <Select
              value={edits.sentiment}
              onChange={(v) => setField("sentiment", v || "neutral")}
              options={SENTIMENT_OPTIONS}
            />
          </div>
          <div>
            <label className="label">Topics</label>
            <TagInput value={edits.topics} onChange={(v) => setField("topics", v)} placeholder="Add topic and press Enter" />
          </div>
          <div>
            <label className="label">Competitors Mentioned</label>
            <TagInput value={edits.competitor_mentions} onChange={(v) => setField("competitor_mentions", v)} placeholder="Add competitor and press Enter" />
          </div>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="label mb-0">Action Items</label>
          <button onClick={addItem} className="text-xs text-brand-600 hover:text-brand-700 font-medium">
            + Add action item
          </button>
        </div>
        <div className="space-y-2">
          {actionItems.length === 0 && (
            <p className="text-xs text-slate-400">No action items extracted.</p>
          )}
          {actionItems.map((item, idx) => (
            <div key={item.id || `new-${idx}`} className="flex flex-col md:flex-row gap-2 p-3 border border-slate-200 rounded-lg bg-slate-50">
              <input
                type="text"
                value={item.description}
                onChange={(e) => updateItem(idx, { description: e.target.value })}
                placeholder="Describe the action..."
                className="input flex-1 bg-white"
              />
              <input
                type="date"
                value={item.due_date || ""}
                onChange={(e) => updateItem(idx, { due_date: e.target.value })}
                className="input md:w-40 bg-white"
              />
              <div className="md:w-32">
                <Select size="sm"
                  value={item.priority}
                  onChange={(v) => updateItem(idx, { priority: v })}
                  options={PRIORITY_OPTIONS}
                />
              </div>
              <button
                onClick={() => removeItem(idx)}
                className="text-slate-400 hover:text-red-600 px-2 self-center"
                title="Remove"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
        <button
          onClick={() => confirmMutation.mutate()}
          disabled={confirmMutation.isPending}
          className="btn-primary flex items-center gap-2"
        >
          {confirmMutation.isPending && <Loader2 size={15} className="animate-spin" />}
          Confirm & Push to CRM
        </button>
      </div>
    </div>
  );
}

function ReviewField({ label, rows, value, onChange }) {
  return (
    <div>
      <label className="label">{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        className="input text-sm leading-relaxed"
      />
    </div>
  );
}

function TagInput({ value, onChange, placeholder }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const t = draft.trim();
    if (t && !value.includes(t)) onChange([...value, t]);
    setDraft("");
  };
  const remove = (t) => onChange(value.filter((v) => v !== t));
  return (
    <div className="flex flex-wrap items-center gap-1.5 input min-h-[42px] py-1.5">
      {value.map((t) => (
        <span key={t} className="badge bg-blue-100 text-blue-700 flex items-center gap-1">
          {t}
          <button onClick={() => remove(t)} className="hover:text-red-600">×</button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(); }
        }}
        onBlur={add}
        placeholder={value.length === 0 ? placeholder : ""}
        className="flex-1 min-w-[100px] outline-none text-sm bg-transparent"
      />
    </div>
  );
}
