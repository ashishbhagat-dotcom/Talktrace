import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Clock, CheckCircle } from "lucide-react";
import { getActionItems, getMyActionItems, getOverdueActionItems, updateActionItem } from "../api/actionItems";
import { formatDate } from "../utils/formatters";
import toast from "react-hot-toast";

const TABS = [
  { key: "all", label: "All" },
  { key: "my", label: "My Items" },
  { key: "overdue", label: "Overdue" },
];

const PRIORITY_COLORS = {
  urgent: "bg-red-100 text-red-700",
  high: "bg-orange-100 text-orange-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-slate-100 text-slate-600",
};

export default function ActionItems() {
  const [tab, setTab] = useState("all");
  const queryClient = useQueryClient();

  const fetchFn = tab === "my" ? getMyActionItems : tab === "overdue" ? getOverdueActionItems : getActionItems;

  const { data, isLoading } = useQuery({
    queryKey: ["action-items", tab],
    queryFn: () => fetchFn().then((r) => r.data),
  });

  const update = useMutation({
    mutationFn: ({ id, status }) => updateActionItem(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries(["action-items"]);
      toast.success("Updated");
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Action Items</h1>
        <p className="text-slate-500 mt-1">Track and manage follow-up tasks from conversations.</p>
      </div>

      <div className="card">
        <div className="flex border-b border-slate-200 px-4">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px ${
                tab === key
                  ? "border-brand-500 text-brand-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-16 bg-slate-100 animate-pulse rounded-lg" />
            ))}
          </div>
        ) : data?.results?.length === 0 || data?.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <CheckCircle size={32} className="mx-auto mb-3 text-slate-300" />
            <p className="font-medium">No action items here</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {(data?.results || data || []).map((item) => {
              const isOverdue =
                item.due_date &&
                new Date(item.due_date) < new Date() &&
                !["completed", "cancelled"].includes(item.status);

              return (
                <div key={item.id} className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 px-4 md:px-6 py-4">
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm text-slate-800 ${item.status === "completed" ? "line-through text-slate-400" : ""}`}>
                      {item.description}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 sm:gap-3 mt-1">
                      {item.conversation_id && (
                        <Link
                          to={`/conversations/${item.conversation_id}`}
                          className="text-xs text-brand-600 hover:underline"
                        >
                          View conversation
                        </Link>
                      )}
                      {item.due_date && (
                        <span className={`text-xs ${isOverdue ? "text-red-500 font-medium" : "text-slate-400"}`}>
                          {isOverdue && <AlertCircle size={10} className="inline mr-0.5" />}
                          Due {formatDate(item.due_date)}
                        </span>
                      )}
                      {item.assigned_to && (
                        <span className="text-xs text-slate-400">→ {item.assigned_to.name}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={`badge ${PRIORITY_COLORS[item.priority] || ""}`}>
                      {item.priority}
                    </span>
                    <select
                      value={item.status}
                      onChange={(e) => update.mutate({ id: item.id, status: e.target.value })}
                      className="input-sm"
                    >
                      <option value="pending">Pending</option>
                      <option value="in_progress">In Progress</option>
                      <option value="completed">Completed</option>
                      <option value="cancelled">Cancelled</option>
                    </select>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
