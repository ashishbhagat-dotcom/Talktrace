import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, MessageSquare, CheckSquare, TrendingUp, Users } from "lucide-react";
import { getSummary } from "../api/analytics";
import { getConversations } from "../api/conversations";
import SentimentBadge from "../components/conversations/SentimentBadge";
import { timeAgo, conversationTypeLabel } from "../utils/formatters";
import useAuthStore from "../store/authStore";

function StatCard({ label, value, icon: Icon, color = "brand" }) {
  return (
    <div className="card p-6 flex items-center gap-4">
      <div className={`w-12 h-12 bg-${color}-100 rounded-xl flex items-center justify-center flex-shrink-0`}>
        <Icon size={22} className={`text-${color}-600`} />
      </div>
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        <p className="text-2xl font-bold text-slate-800">{value ?? "—"}</p>
      </div>
    </div>
  );
}

function Skeleton({ className }) {
  return <div className={`bg-slate-200 animate-pulse rounded-lg ${className}`} />;
}

export default function Dashboard() {
  const user = useAuthStore((s) => s.user);

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["analytics-summary"],
    queryFn: () => getSummary({ days: 30 }).then((r) => r.data),
  });

  const { data: recent, isLoading: recentLoading } = useQuery({
    queryKey: ["conversations-recent"],
    queryFn: () => getConversations({ page_size: 10 }).then((r) => r.data),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-slate-800">
            Good {getTimeOfDay()}, {user?.name?.split(" ")[0]}
          </h1>
          <p className="text-slate-500 mt-1 text-sm md:text-base">Here's what's happening with your conversations.</p>
        </div>
        <Link to="/conversations/new" className="btn-primary flex-shrink-0">
          <Plus size={16} />
          <span className="hidden sm:inline">New Conversation</span>
          <span className="sm:hidden">New</span>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {summaryLoading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)
        ) : (
          <>
            <StatCard label="Conversations (30d)" value={summary?.total_conversations} icon={MessageSquare} color="brand" />
            <StatCard label="Pending Actions" value={summary?.pending_actions} icon={CheckSquare} color="orange" />
            <StatCard label="Overdue Actions" value={summary?.overdue_actions} icon={CheckSquare} color="red" />
            <StatCard label="Active Customers" value={summary?.active_customers} icon={Users} color="purple" />
          </>
        )}
      </div>

      {/* Recent conversations */}
      <div className="card">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-800">Recent Conversations</h2>
          <Link to="/search" className="text-sm text-brand-600 hover:text-brand-700 font-medium">
            View all
          </Link>
        </div>

        {recentLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : recent?.results?.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <MessageSquare size={32} className="mx-auto mb-3 text-slate-300" />
            <p className="font-medium">No conversations yet</p>
            <p className="text-sm mt-1">
              <Link to="/conversations/new" className="text-brand-600 hover:underline">
                Capture your first conversation
              </Link>
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {recent?.results?.map((conv) => (
              <Link
                key={conv.id}
                to={`/conversations/${conv.id}`}
                className="flex items-center justify-between px-6 py-4 hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-10 h-10 bg-brand-100 rounded-lg flex items-center justify-center flex-shrink-0">
                    <MessageSquare size={16} className="text-brand-600" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-slate-800 truncate">
                      {conv.customer?.name}
                      {conv.customer?.company && (
                        <span className="text-slate-400 font-normal"> · {conv.customer.company}</span>
                      )}
                    </p>
                    <p className="text-sm text-slate-500 truncate">
                      {conv.summary_preview || "Processing..."}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                  <SentimentBadge sentiment={conv.sentiment} />
                  <span className="text-xs text-slate-400">{timeAgo(conv.interaction_date)}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function getTimeOfDay() {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}
