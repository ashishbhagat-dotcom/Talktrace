import { create } from "zustand";

const isMobile = () => typeof window !== "undefined" && window.innerWidth < 768;

const useUIStore = create((set) => ({
  sidebarOpen: !isMobile(),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));

export default useUIStore;
