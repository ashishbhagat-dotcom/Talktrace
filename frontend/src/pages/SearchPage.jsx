import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search, Loader2 } from "lucide-react";
import { search } from "../api/search";
import { useDebounce } from "../hooks/useDebounce";
import SentimentBadge from "../components/conversations/SentimentBadge";
import { timeAgo, conversationTypeLabel } from "../utils/formatters";

const MODES = [
  { value: "keyword", label: "Keyword" },
  { value: "semantic", label: "Semantic" },
  { value: "hybrid", label: "Hybrid" },
];

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("hybrid");
  const debouncedQuery = useDebounce(query, 500);

  const { data, isLoading } = useQuery({
    queryKey: ["search", debouncedQuery, mode],
    queryFn: () => search({ q: debouncedQuery, mode }).then((r) => r.data),
    enabled: true,
  });

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Search Conversations</h1>
        <p className="text-slate-500 mt-1">Find conversations by keyword, meaning, or both.</p>
      </div>

      {/* Search bar + mode */}
      <div className="card p-4 space-y-3">
        <div className="relative">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            className="input pl-11 py-3 text-base"
            placeholder="Search by customer name, topic, requirement, competitor..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium">Search mode:</span>
          {MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => setMode(m.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                mode === m.value
                  ? "bg-brand-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 size={24} className="animate-spin text-slate-400" />
        </div>
      ) : (
        <div>
          {data?.count !== undefined && (
            <p className="text-sm text-slate-500 mb-3">
              {data.count} conversation{data.count !== 1 ? "s" : ""} found
            </p>
          )}
          <div className="space-y-3">
            {data?.results?.map((conv) => (
              <Link
                key={conv.id}
                to={`/conversations/${conv.id}`}
                className="card p-5 flex items-start gap-4 hover:border-brand-300 transition-colors block"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="font-semibold text-slate-800">{conv.customer?.name}</span>
                    {conv.customer?.company && (
                      <span className="text-slate-400 text-sm">{conv.customer.company}</span>
                    )}
                    <span className="badge bg-slate-100 text-slate-600">
                      {conversationTypeLabel(conv.conversation_type)}
                    </span>
                  </div>
                  <p className="text-sm text-slate-600 leading-relaxed line-clamp-2">
                    {conv.summary_preview}
                  </p>
                  {conv.topics?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {conv.topics.slice(0, 4).map((t) => (
                        <span key={t} className="badge bg-blue-50 text-blue-600">{t}</span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2 flex-shrink-0">
                  <SentimentBadge sentiment={conv.sentiment} />
                  <span className="text-xs text-slate-400">{timeAgo(conv.interaction_date)}</span>
                </div>
              </Link>
            ))}
            {data?.results?.length === 0 && (
              <div className="text-center py-12 text-slate-500">
                <Search size={32} className="mx-auto mb-3 text-slate-300" />
                <p className="font-medium">No conversations found</p>
                <p className="text-sm mt-1">Try different keywords or switch to Semantic mode</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
