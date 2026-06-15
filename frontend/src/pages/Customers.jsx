import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search, Building2, Mail, Phone, ExternalLink } from "lucide-react";
import { getCustomers } from "../api/customers";
import Select from "../components/ui/Select";

const TYPE_STYLES = {
  lead: "bg-yellow-100 text-yellow-700",
  contact: "bg-blue-100 text-blue-700",
  account: "bg-purple-100 text-purple-700",
};

function CustomerCard({ customer }) {
  return (
    <Link
      to={`/customers/${customer.id}`}
      className="card p-5 hover:shadow-md transition-shadow flex flex-col gap-3"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-semibold text-slate-800 truncate">{customer.name}</h3>
          {customer.company && (
            <div className="flex items-center gap-1 text-sm text-slate-500 mt-0.5 truncate">
              <Building2 size={12} className="flex-shrink-0" />
              <span className="truncate">{customer.company}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {customer.zoho_record_id && (
            <span className="text-xs bg-green-50 text-green-600 border border-green-200 px-1.5 py-0.5 rounded font-medium">
              Zoho
            </span>
          )}
          <span className={`badge capitalize ${TYPE_STYLES[customer.type] || "bg-slate-100 text-slate-600"}`}>
            {customer.type}
          </span>
        </div>
      </div>

      <div className="space-y-1">
        {customer.email && (
          <div className="flex items-center gap-1.5 text-xs text-slate-500 truncate">
            <Mail size={11} className="flex-shrink-0" />
            <span className="truncate">{customer.email}</span>
          </div>
        )}
        {customer.phone && (
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Phone size={11} className="flex-shrink-0" />
            <span>{customer.phone}</span>
          </div>
        )}
      </div>

      {customer.conversation_count > 0 && (
        <div className="text-xs text-slate-400 pt-1 border-t border-slate-100">
          {customer.conversation_count} conversation{customer.conversation_count !== 1 ? "s" : ""}
        </div>
      )}
    </Link>
  );
}

export default function Customers() {
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["customers", search, type, page],
    queryFn: () =>
      getCustomers({ q: search || undefined, type: type || undefined, page }).then((r) => r.data),
    keepPreviousData: true,
  });

  const handleSearch = (e) => {
    setSearch(e.target.value);
    setPage(1);
  };

  const handleType = (v) => {
    setType(v || "");
    setPage(1);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Customers</h1>
          <p className="text-slate-500 mt-1">
            {data?.count != null ? `${data.count} total` : ""}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by name, email, company..."
            value={search}
            onChange={handleSearch}
            className="input pl-9 w-full"
          />
        </div>
        <div className="w-40">
          <Select
            value={type}
            onChange={handleType}
            placeholder="All types"
            allowClear
            options={[
              { value: "lead", label: "Lead" },
              { value: "contact", label: "Contact" },
              { value: "account", label: "Account" },
            ]}
          />
        </div>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(9)].map((_, i) => (
            <div key={i} className="h-36 bg-slate-200 animate-pulse rounded-xl" />
          ))}
        </div>
      ) : data?.results?.length === 0 ? (
        <div className="card p-16 text-center text-slate-400">
          <p className="text-lg font-medium mb-1">No customers found</p>
          <p className="text-sm">Try adjusting your filters or sync from Zoho in Settings.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data?.results?.map((c) => (
            <CustomerCard key={c.id} customer={c} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {data?.total_pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => p - 1)}
            disabled={page === 1}
            className="btn-secondary text-sm disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-sm text-slate-500">
            Page {data.current_page} of {data.total_pages}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page === data.total_pages}
            className="btn-secondary text-sm disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
