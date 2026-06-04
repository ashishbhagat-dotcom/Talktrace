import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, CheckCircle2, XCircle, RefreshCw, Link2, Unlink } from "lucide-react";
import { getMe, updateProfile } from "../api/auth";
import { getZohoStatus, getZohoConnectUrl, disconnectZoho, triggerZohoSync } from "../api/integrations";
import useAuthStore from "../store/authStore";
import toast from "react-hot-toast";
import { formatDateTime } from "../utils/formatters";

function ZohoIntegrationCard() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const { data: statusRes, isLoading } = useQuery({
    queryKey: ["zoho-status"],
    queryFn: () => getZohoStatus().then((r) => r.data),
    retry: false,
  });

  // Handle callback redirect from Zoho
  useEffect(() => {
    const zohoParam = searchParams.get("zoho");
    if (zohoParam === "connected") {
      toast.success("Zoho CRM connected! Initial sync started.");
      queryClient.invalidateQueries(["zoho-status"]);
      setSearchParams({});
    } else if (zohoParam === "error") {
      const reason = searchParams.get("reason") || "unknown error";
      toast.error(`Zoho connection failed: ${reason}`);
      setSearchParams({});
    }
  }, [searchParams, queryClient, setSearchParams]);

  const connectMutation = useMutation({
    mutationFn: () => getZohoConnectUrl().then((r) => r.data.auth_url),
    onSuccess: (authUrl) => {
      window.location.href = authUrl;
    },
    onError: (err) => {
      const msg = err.response?.data?.error || "Zoho is not configured on this server.";
      toast.error(msg);
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: disconnectZoho,
    onSuccess: () => {
      queryClient.invalidateQueries(["zoho-status"]);
      toast.success("Zoho CRM disconnected");
    },
    onError: () => toast.error("Failed to disconnect"),
  });

  const syncMutation = useMutation({
    mutationFn: triggerZohoSync,
    onSuccess: () => toast.success("Sync started — contacts and leads will import shortly"),
    onError: () => toast.error("Sync failed to start"),
  });

  const connected = statusRes?.connected;

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="font-semibold text-slate-800 flex items-center gap-2">
            <img
              src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Zoho_logo.svg/200px-Zoho_logo.svg.png"
              alt="Zoho"
              className="h-5 object-contain"
              onError={(e) => { e.target.style.display = "none"; }}
            />
            Zoho CRM
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Sync contacts and leads from Zoho. Automatically push AI summaries as CRM notes.
          </p>
        </div>
        {isLoading ? (
          <Loader2 size={18} className="animate-spin text-slate-400" />
        ) : connected ? (
          <span className="flex items-center gap-1.5 text-xs font-medium text-green-600 bg-green-50 px-2.5 py-1 rounded-full">
            <CheckCircle2 size={13} /> Connected
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full">
            <XCircle size={13} /> Not connected
          </span>
        )}
      </div>

      {connected && (
        <div className="bg-slate-50 rounded-lg px-4 py-3 mb-4 space-y-1 text-sm">
          {statusRes.zoho_user_email && (
            <p className="text-slate-600">
              <span className="font-medium">Account:</span> {statusRes.zoho_user_email}
            </p>
          )}
          <p className="text-slate-600">
            <span className="font-medium">Last synced:</span>{" "}
            {statusRes.last_sync_at ? formatDateTime(statusRes.last_sync_at) : "Never"}
          </p>
        </div>
      )}

      <div className="flex gap-2 flex-wrap">
        {connected ? (
          <>
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="btn-secondary flex items-center gap-1.5 text-sm"
            >
              {syncMutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              Sync Now
            </button>
            <button
              onClick={() => disconnectMutation.mutate()}
              disabled={disconnectMutation.isPending}
              className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition-colors"
            >
              {disconnectMutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Unlink size={14} />
              )}
              Disconnect
            </button>
          </>
        ) : (
          <button
            onClick={() => connectMutation.mutate()}
            disabled={connectMutation.isPending}
            className="btn-primary flex items-center gap-1.5 text-sm"
          >
            {connectMutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Link2 size={14} />
            )}
            Connect Zoho CRM
          </button>
        )}
      </div>

      <div className="mt-4 border-t border-slate-100 pt-4">
        <p className="text-xs text-slate-400 font-medium mb-2">What syncs:</p>
        <ul className="text-xs text-slate-500 space-y-1">
          <li>→ Zoho Contacts and Leads → Talktrace Customers (every 30 min)</li>
          <li>← AI conversation summaries → Zoho CRM Notes (after each analysis)</li>
        </ul>
      </div>
    </div>
  );
}

export default function Settings() {
  const { user, setUser } = useAuthStore();
  const queryClient = useQueryClient();
  const [name, setName] = useState(user?.name || "");

  const update = useMutation({
    mutationFn: (data) => updateProfile(data),
    onSuccess: ({ data }) => {
      setUser(data);
      queryClient.invalidateQueries(["me"]);
      toast.success("Profile updated");
    },
    onError: () => toast.error("Failed to update profile"),
  });

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Settings</h1>
        <p className="text-slate-500 mt-1">Manage your account and integrations.</p>
      </div>

      <div className="card p-6">
        <h2 className="font-semibold text-slate-800 mb-4">Profile</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            update.mutate({ name });
          }}
          className="space-y-4"
        >
          <div>
            <label className="label">Full Name</label>
            <input
              type="text"
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Email</label>
            <input type="email" className="input bg-slate-50" value={user?.email} disabled />
            <p className="text-xs text-slate-400 mt-1">Email cannot be changed</p>
          </div>
          <div>
            <label className="label">Role</label>
            <input type="text" className="input bg-slate-50 capitalize" value={user?.role} disabled />
          </div>
          <button type="submit" disabled={update.isPending} className="btn-primary">
            {update.isPending && <Loader2 size={15} className="animate-spin" />}
            Save Changes
          </button>
        </form>
      </div>

      <div>
        <h2 className="font-semibold text-slate-800 mb-3">Integrations</h2>
        <ZohoIntegrationCard />
      </div>
    </div>
  );
}
