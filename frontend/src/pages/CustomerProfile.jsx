import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Mail, Phone, Building2 } from "lucide-react";
import { getCustomer, getCustomerTimeline } from "../api/customers";
import SentimentBadge from "../components/conversations/SentimentBadge";
import { timeAgo, conversationTypeLabel } from "../utils/formatters";

export default function CustomerProfile() {
  const { id } = useParams();

  const { data: customer, isLoading: custLoading } = useQuery({
    queryKey: ["customer", id],
    queryFn: () => getCustomer(id).then((r) => r.data),
  });

  const { data: timeline, isLoading: timelineLoading } = useQuery({
    queryKey: ["customer-timeline", id],
    queryFn: () => getCustomerTimeline(id).then((r) => r.data),
  });

  if (custLoading) {
    return (
      <div className="space-y-4">
        <div className="h-40 bg-slate-200 animate-pulse rounded-xl" />
        <div className="h-64 bg-slate-200 animate-pulse rounded-xl" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700">
        <ArrowLeft size={14} />
        Back
      </Link>

      {/* Customer header */}
      <div className="card p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">{customer?.name}</h1>
            {customer?.company && (
              <div className="flex items-center gap-1 text-slate-500 mt-1">
                <Building2 size={14} />
                <span>{customer.company}</span>
              </div>
            )}
            <div className="flex items-center gap-4 mt-3">
              {customer?.email && (
                <a href={`mailto:${customer.email}`} className="flex items-center gap-1 text-sm text-brand-600 hover:underline">
                  <Mail size={14} />
                  {customer.email}
                </a>
              )}
              {customer?.phone && (
                <span className="flex items-center gap-1 text-sm text-slate-500">
                  <Phone size={14} />
                  {customer.phone}
                </span>
              )}
            </div>
          </div>
          <span className="badge bg-brand-100 text-brand-700 capitalize">{customer?.type}</span>
        </div>
        {customer?.notes && (
          <div className="mt-4 pt-4 border-t border-slate-100 text-sm text-slate-600">
            {customer.notes}
          </div>
        )}
      </div>

      {/* Conversation timeline */}
      <div className="card">
        <div className="px-6 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-800">
            Conversation History ({timeline?.count || 0})
          </h2>
        </div>

        {timelineLoading ? (
          <div className="p-4 space-y-3">
            {[1, 2, 3].map((i) => <div key={i} className="h-20 bg-slate-100 animate-pulse rounded-lg" />)}
          </div>
        ) : timeline?.results?.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <p>No conversations yet</p>
            <Link to="/conversations/new" className="text-brand-600 hover:underline text-sm mt-1 inline-block">
              Start a conversation
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {timeline?.results?.map((conv) => (
              <Link
                key={conv.id}
                to={`/conversations/${conv.id}`}
                className="flex items-center gap-4 px-6 py-4 hover:bg-slate-50 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-slate-700">
                      {conversationTypeLabel(conv.conversation_type)}
                    </span>
                    <span className="text-xs text-slate-400">{timeAgo(conv.interaction_date)}</span>
                  </div>
                  <p className="text-sm text-slate-500 truncate">{conv.summary_preview}</p>
                </div>
                <SentimentBadge sentiment={conv.sentiment} />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
