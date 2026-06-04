import { Routes, Route, Navigate } from "react-router-dom";
import useAuthStore from "./store/authStore";
import AppLayout from "./components/layout/AppLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import NewConversation from "./pages/NewConversation";
import ConversationView from "./pages/ConversationView";
import SearchPage from "./pages/SearchPage";
import CustomerProfile from "./pages/CustomerProfile";
import ActionItems from "./pages/ActionItems";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";
import Customers from "./pages/Customers";
import Users from "./pages/Users";

function ProtectedRoute({ children }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="conversations/new" element={<NewConversation />} />
        <Route path="conversations/:id" element={<ConversationView />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="customers" element={<Customers />} />
        <Route path="users" element={<Users />} />
        <Route path="customers/:id" element={<CustomerProfile />} />
        <Route path="action-items" element={<ActionItems />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
