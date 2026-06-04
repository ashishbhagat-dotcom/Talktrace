import { useState, useRef, useEffect } from "react";
import { Search, X } from "lucide-react";
import { useDebounce } from "../../hooks/useDebounce";
import { searchCustomers } from "../../api/customers";

export default function CustomerSearch({ value, onChange, placeholder = "Search customers..." }) {
  const [query, setQuery] = useState(value?.name || "");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debouncedQuery = useDebounce(query, 300);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!debouncedQuery.trim() || debouncedQuery === value?.name) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    searchCustomers(debouncedQuery)
      .then(({ data }) => {
        setResults(data);
        setOpen(true);
      })
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, [debouncedQuery]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const select = (customer) => {
    setQuery(customer.name);
    setOpen(false);
    onChange(customer);
  };

  const clear = () => {
    setQuery("");
    onChange(null);
    setResults([]);
  };

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          className="input pl-9 pr-8"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
        />
        {query && (
          <button onClick={clear} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
            <X size={14} />
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden">
          {results.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => select(c)}
              className="w-full text-left px-4 py-2.5 hover:bg-slate-50 transition-colors"
            >
              <p className="text-sm font-medium text-slate-800">{c.name}</p>
              {c.company && <p className="text-xs text-slate-500">{c.company}</p>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
