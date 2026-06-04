import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, CheckCircle, Clock, AlertCircle } from "lucide-react";
import { getConversation } from "../api/conversations";
import { updateActionItem } from "../api/actionItems";
import SentimentBadge from "../components/conversations/SentimentBadge";
import AIProcessingStatus from "../components/conversations/AIProcessingStatus";
import { formatDate, formatDateTime, conversationTypeLabel } from "../utils/formatters";
import toast from "react-hot-toast";

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
    refetchInterval: (query) =>
      query.state.data?.ai_status !== "completed" ? 3000 : false,
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

      {/* AI Processing */}
      {conversation.ai_status !== "completed" && (
        <AIProcessingStatus
          conversationId={id}
          hasAudio={conversation.attachments?.length > 0}
        />
      )}

      {/* Main content grid */}
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

      {/* Action Items */}
      {conversation.action_items?.length > 0 && (
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
                <select
                  value={item.status}
                  onChange={(e) => updateStatus.mutate({ itemId: item.id, status: e.target.value })}
                  className="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white flex-shrink-0"
                >
                  <option value="pending">Pending</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
