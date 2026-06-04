import { useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { clsx } from "clsx";
import {
  LayoutDashboard, Plus, Search, Users, CheckSquare,
  BarChart2, Settings, MessageSquare, ChevronLeft, ChevronRight, UserCircle,
} from "lucide-react";
import useUIStore from "../../store/uiStore";

const NAV = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/conversations/new", icon: Plus, label: "New Conversation" },
  { to: "/search", icon: Search, label: "Search" },
  { to: "/customers", icon: Users, label: "Customers" },
  { to: "/users", icon: UserCircle, label: "Users" },
  { to: "/action-items", icon: CheckSquare, label: "Action Items" },
  { to: "/analytics", icon: BarChart2, label: "Analytics" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  const { sidebarOpen, toggleSidebar, setSidebarOpen } = useUIStore();
  const location = useLocation();

  // Close sidebar on mobile when navigating
  useEffect(() => {
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  }, [location.pathname, setSidebarOpen]);

  // Close on resize to desktop
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth >= 768 && !sidebarOpen) {
        setSidebarOpen(true);
      }
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [sidebarOpen, setSidebarOpen]);

  return (
    <>
      {/* Mobile overlay backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={clsx(
          "fixed left-0 top-0 h-full bg-slate-900 text-white flex flex-col z-30 transition-all duration-200",
          // Mobile: full drawer, slide in/out
          "max-md:w-64",
          sidebarOpen ? "max-md:translate-x-0" : "max-md:-translate-x-full",
          // Desktop: collapsible icon/full
          "md:translate-x-0",
          sidebarOpen ? "md:w-64" : "md:w-16"
        )}
      >
        {/* Logo */}
        <div className="flex items-center h-16 px-4 border-b border-slate-800 flex-shrink-0">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-8 h-8 bg-brand-500 rounded-lg flex items-center justify-center flex-shrink-0">
              <MessageSquare size={16} className="text-white" />
            </div>
            {sidebarOpen && (
              <span className="font-semibold text-lg whitespace-nowrap">Talktrace</span>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 overflow-y-auto">
          {NAV.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-brand-600 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                )
              }
              title={!sidebarOpen ? label : undefined}
            >
              <Icon size={18} className="flex-shrink-0" />
              {sidebarOpen && <span className="whitespace-nowrap">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Toggle — desktop only */}
        <button
          onClick={toggleSidebar}
          className="hidden md:flex items-center justify-center h-12 border-t border-slate-800 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors flex-shrink-0"
          title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
        >
          {sidebarOpen ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </button>
      </aside>
    </>
  );
}
