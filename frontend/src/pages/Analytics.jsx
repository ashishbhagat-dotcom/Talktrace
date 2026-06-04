import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie
} from "recharts";
import { getVolume, getSentiment, getTeamActivity, getTopics, getFollowUps } from "../api/analytics";

const DATE_RANGES = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
];

const SENTIMENT_COLORS = {
  very_negative: "#ef4444",
  negative: "#f97316",
  neutral: "#94a3b8",
  positive: "#22c55e",
  very_positive: "#10b981",
};

function ChartCard({ title, children, isLoading }) {
  return (
    <div className="card p-6">
      <h3 className="font-semibold text-slate-800 mb-4">{title}</h3>
      {isLoading ? (
        <div className="h-48 bg-slate-100 animate-pulse rounded-lg" />
      ) : (
        children
      )}
    </div>
  );
}

export default function Analytics() {
  const [days, setDays] = useState(30);
  const params = { days };

  const { data: volume, isLoading: volumeLoading } = useQuery({
    queryKey: ["analytics-volume", days],
    queryFn: () => getVolume(params).then((r) => r.data),
  });

  const { data: sentiment, isLoading: sentimentLoading } = useQuery({
    queryKey: ["analytics-sentiment", days],
    queryFn: () => getSentiment(params).then((r) => r.data),
  });

  const { data: team, isLoading: teamLoading } = useQuery({
    queryKey: ["analytics-team", days],
    queryFn: () => getTeamActivity(params).then((r) => r.data),
  });

  const { data: topics, isLoading: topicsLoading } = useQuery({
    queryKey: ["analytics-topics", days],
    queryFn: () => getTopics(params).then((r) => r.data),
  });

  const { data: followups, isLoading: followupsLoading } = useQuery({
    queryKey: ["analytics-followups", days],
    queryFn: () => getFollowUps(params).then((r) => r.data),
  });

  const pieData = followups
    ? [
        { name: "Completed", value: followups.completed, fill: "#22c55e" },
        { name: "In Progress", value: followups.in_progress, fill: "#3b82f6" },
        { name: "Pending", value: followups.pending, fill: "#f59e0b" },
        { name: "Overdue", value: followups.overdue, fill: "#ef4444" },
      ].filter((d) => d.value > 0)
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Analytics</h1>
          <p className="text-slate-500 mt-1">Conversation insights and team performance.</p>
        </div>
        <div className="flex gap-2">
          {DATE_RANGES.map(({ label, days: d }) => (
            <button
              key={label}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                days === d ? "bg-brand-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
              }`}
            >
              Last {label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Volume */}
        <ChartCard title="Conversation Volume" isLoading={volumeLoading}>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={volume} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d?.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Sentiment trend */}
        <ChartCard title="Sentiment Trend" isLoading={sentimentLoading}>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={sentiment?.trend} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => d?.slice(5)} />
              <YAxis domain={[-1, 1]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="avg_score" stroke="#0ea5e9" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Team activity */}
        <ChartCard title="Team Activity" isLoading={teamLoading}>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={team} layout="vertical" margin={{ top: 0, right: 0, bottom: 0, left: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="user_name" type="category" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="conversations" fill="#0ea5e9" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Topics */}
        <ChartCard title="Top Topics" isLoading={topicsLoading}>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={topics?.slice(0, 8)} layout="vertical" margin={{ top: 0, right: 0, bottom: 0, left: 80 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="topic" type="category" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Follow-up rate */}
        <ChartCard title="Action Item Status" isLoading={followupsLoading}>
          {pieData.length > 0 ? (
            <div className="flex items-center gap-6">
              <ResponsiveContainer width={160} height={160}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={70} dataKey="value">
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2">
                {pieData.map((d) => (
                  <div key={d.name} className="flex items-center gap-2 text-sm">
                    <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: d.fill }} />
                    <span className="text-slate-600">{d.name}:</span>
                    <span className="font-medium text-slate-800">{d.value}</span>
                  </div>
                ))}
                {followups?.completion_rate !== undefined && (
                  <p className="text-sm text-slate-500 pt-2 border-t border-slate-100">
                    Completion rate: <strong>{followups.completion_rate}%</strong>
                  </p>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-400 text-center py-8">No action items in this period</p>
          )}
        </ChartCard>

        {/* Sentiment distribution */}
        <ChartCard title="Sentiment Distribution" isLoading={sentimentLoading}>
          {sentiment?.distribution?.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={sentiment.distribution} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="sentiment" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {sentiment?.distribution?.map((entry) => (
                    <Cell key={entry.sentiment} fill={SENTIMENT_COLORS[entry.sentiment] || "#94a3b8"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-slate-400 text-center py-8">No sentiment data yet</p>
          )}
        </ChartCard>
      </div>
    </div>
  );
}
