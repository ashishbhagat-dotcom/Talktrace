import { Outlet } from "react-router-dom";
import { clsx } from "clsx";
import Sidebar from "./Sidebar";
import Header from "./Header";
import useUIStore from "../../store/uiStore";

export default function AppLayout() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      <Sidebar />
      <div
        className={clsx(
          "flex flex-col flex-1 min-w-0 transition-all duration-200",
          // Mobile: no margin — sidebar is an overlay
          "ml-0",
          // Desktop: margin matches sidebar width
          sidebarOpen ? "md:ml-64" : "md:ml-16"
        )}
      >
        <Header />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
