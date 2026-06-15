import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { UserPlus, Loader2, ShieldCheck, User, Users as UsersIcon } from "lucide-react";
import { getUsers, createUser, updateUser, deactivateUser, activateUser } from "../api/users";
import useAuthStore from "../store/authStore";
import toast from "react-hot-toast";
import { formatDate } from "../utils/formatters";

const ROLE_STYLES = {
  admin: "bg-purple-100 text-purple-700",
  manager: "bg-blue-100 text-blue-700",
  member: "bg-slate-100 text-slate-600",
};

const ROLE_ICONS = {
  admin: ShieldCheck,
  manager: User,
  member: User,
};

function validatePassword(pw) {
  if (!pw) return null;
  if (pw.length < 8) return "Password must be at least 8 characters.";
  if (/^\d+$/.test(pw)) return "Password cannot be entirely numeric.";
  const common = ["password", "12345678", "qwerty123", "letmein", "welcome"];
  if (common.some((c) => pw.toLowerCase().includes(c))) return "Password is too common.";
  return null;
}

function FormField({ label, error, children }) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  );
}

function CreateUserModal({ onClose }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", email: "", role: "member", password: "" });
  const [fieldErrors, setFieldErrors] = useState({});

  const create = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries(["users"]);
      toast.success("User created successfully");
      onClose();
    },
    onError: (err) => {
      const data = err.response?.data;
      if (data && typeof data === "object") {
        const mapped = {};
        for (const [key, val] of Object.entries(data)) {
          mapped[key] = Array.isArray(val) ? val[0] : String(val);
        }
        setFieldErrors(mapped);
      } else {
        toast.error("Failed to create user");
      }
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    const pwError = validatePassword(form.password);
    if (pwError) { setFieldErrors({ password: pwError }); return; }
    setFieldErrors({});
    create.mutate(form);
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-800">Add New User</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <FormField label="Full Name" error={fieldErrors.name}>
            <input
              className={`input ${fieldErrors.name ? "border-red-400" : ""}`}
              placeholder="Jane Smith"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </FormField>
          <FormField label="Email" error={fieldErrors.email}>
            <input
              type="email"
              className={`input ${fieldErrors.email ? "border-red-400" : ""}`}
              placeholder="jane@company.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </FormField>
          <FormField label="Role" error={fieldErrors.role}>
            <select
              className="input"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              <option value="member">Member — can create and view conversations</option>
              <option value="manager">Manager — can manage team conversations</option>
              <option value="admin">Admin — full access including user management</option>
            </select>
          </FormField>
          <FormField label="Password" error={fieldErrors.password}>
            <input
              type="password"
              className={`input ${fieldErrors.password ? "border-red-400" : ""}`}
              placeholder="Min. 8 characters"
              value={form.password}
              onChange={(e) => {
                const pw = e.target.value;
                setForm({ ...form, password: pw });
                setFieldErrors((prev) => ({ ...prev, password: validatePassword(pw) }));
              }}
              required
            />
          </FormField>
          <div className="flex gap-2 pt-2">
            <button type="submit" disabled={create.isPending} className="btn-primary flex items-center gap-2">
              {create.isPending ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />}
              Create User
            </button>
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function UserRow({ user, currentUserId }) {
  const queryClient = useQueryClient();
  const [editRole, setEditRole] = useState(null);

  const updateRole = useMutation({
    mutationFn: (role) => updateUser(user.id, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries(["users"]);
      toast.success("Role updated");
      setEditRole(null);
    },
    onError: () => toast.error("Failed to update role"),
  });

  const toggleActive = useMutation({
    mutationFn: () => user.is_active ? deactivateUser(user.id) : activateUser(user.id),
    onSuccess: () => {
      queryClient.invalidateQueries(["users"]);
      toast.success(user.is_active ? "User deactivated" : "User activated");
    },
    onError: () => toast.error("Failed to update user"),
  });

  const RoleIcon = ROLE_ICONS[user.role] || User;
  const isSelf = user.id === currentUserId;

  return (
    <tr className={`border-b border-slate-100 ${!user.is_active ? "opacity-50" : ""}`}>
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-brand-100 text-brand-700 rounded-full flex items-center justify-center text-sm font-semibold flex-shrink-0">
            {user.name?.charAt(0)?.toUpperCase()}
          </div>
          <div>
            <p className="text-sm font-medium text-slate-800">
              {user.name}
              {isSelf && <span className="ml-2 text-xs text-slate-400">(you)</span>}
            </p>
            <p className="text-xs text-slate-500">{user.email}</p>
          </div>
        </div>
      </td>
      <td className="px-6 py-4">
        {editRole !== null ? (
          <select
            className="input-sm"
            value={editRole}
            onChange={(e) => setEditRole(e.target.value)}
            onBlur={() => {
              if (editRole !== user.role) updateRole.mutate(editRole);
              else setEditRole(null);
            }}
            autoFocus
          >
            <option value="member">Member</option>
            <option value="manager">Manager</option>
            <option value="admin">Admin</option>
          </select>
        ) : (
          <button
            onClick={() => !isSelf && setEditRole(user.role)}
            className={`badge capitalize flex items-center gap-1 ${ROLE_STYLES[user.role]} ${!isSelf ? "cursor-pointer hover:opacity-80" : "cursor-default"}`}
            title={isSelf ? "Cannot change your own role" : "Click to change role"}
          >
            <RoleIcon size={11} />
            {user.role}
          </button>
        )}
      </td>
      <td className="px-6 py-4">
        <span className={`badge ${user.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
          {user.is_active ? "Active" : "Inactive"}
        </span>
      </td>
      <td className="px-6 py-4 text-sm text-slate-500">
        {formatDate(user.date_joined)}
      </td>
      <td className="px-6 py-4">
        {!isSelf && (
          <button
            onClick={() => toggleActive.mutate()}
            disabled={toggleActive.isPending}
            className={`text-xs px-3 py-1 rounded-lg border transition-colors ${
              user.is_active
                ? "border-red-200 text-red-600 hover:bg-red-50"
                : "border-green-200 text-green-600 hover:bg-green-50"
            }`}
          >
            {toggleActive.isPending ? (
              <Loader2 size={12} className="animate-spin" />
            ) : user.is_active ? "Deactivate" : "Activate"}
          </button>
        )}
      </td>
    </tr>
  );
}

function MobileUserCard({ user, currentUserId }) {
  const queryClient = useQueryClient();
  const isSelf = user.id === currentUserId;

  const toggleActive = useMutation({
    mutationFn: () => user.is_active ? deactivateUser(user.id) : activateUser(user.id),
    onSuccess: () => {
      queryClient.invalidateQueries(["users"]);
      toast.success(user.is_active ? "User deactivated" : "User activated");
    },
    onError: () => toast.error("Failed to update user"),
  });

  return (
    <div className={`p-4 flex items-center justify-between gap-3 ${!user.is_active ? "opacity-50" : ""}`}>
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-10 h-10 bg-brand-100 text-brand-700 rounded-full flex items-center justify-center text-sm font-semibold flex-shrink-0">
          {user.name?.charAt(0)?.toUpperCase()}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-800 truncate">
            {user.name} {isSelf && <span className="text-xs text-slate-400">(you)</span>}
          </p>
          <p className="text-xs text-slate-500 truncate">{user.email}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className={`badge capitalize text-xs ${ROLE_STYLES[user.role]}`}>{user.role}</span>
            <span className={`badge text-xs ${user.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
              {user.is_active ? "Active" : "Inactive"}
            </span>
          </div>
        </div>
      </div>
      {!isSelf && (
        <button
          onClick={() => toggleActive.mutate()}
          disabled={toggleActive.isPending}
          className={`text-xs px-3 py-1.5 rounded-lg border flex-shrink-0 transition-colors ${
            user.is_active
              ? "border-red-200 text-red-600 hover:bg-red-50"
              : "border-green-200 text-green-600 hover:bg-green-50"
          }`}
        >
          {toggleActive.isPending ? <Loader2 size={12} className="animate-spin" /> : user.is_active ? "Deactivate" : "Activate"}
        </button>
      )}
    </div>
  );
}

export default function Users() {
  const [showCreate, setShowCreate] = useState(false);
  const { user: currentUser } = useAuthStore();

  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => getUsers().then((r) => r.data.results ?? r.data),
  });

  if (currentUser?.role !== "admin") {
    return (
      <div className="max-w-xl mx-auto mt-20 text-center text-slate-500">
        <UsersIcon size={40} className="mx-auto mb-3 text-slate-300" />
        <p className="font-medium">Admin access required</p>
        <p className="text-sm mt-1">Only admins can manage users.</p>
      </div>
    );
  }

  const active = users?.filter((u) => u.is_active).length ?? 0;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Users</h1>
          <p className="text-slate-500 mt-1">
            {users ? `${active} active · ${users.length} total` : ""}
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <UserPlus size={16} />
          Add User
        </button>
      </div>

      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {[1, 2, 3].map((i) => <div key={i} className="h-14 bg-slate-100 animate-pulse rounded-lg" />)}
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50 text-left">
                    <th className="px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wide">User</th>
                    <th className="px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wide">Role</th>
                    <th className="px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wide">Status</th>
                    <th className="px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wide">Joined</th>
                    <th className="px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wide">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users?.map((u) => (
                    <UserRow key={u.id} user={u} currentUserId={currentUser?.id} />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-slate-100">
              {users?.map((u) => (
                <MobileUserCard key={u.id} user={u} currentUserId={currentUser?.id} />
              ))}
            </div>
          </>
        )}
      </div>

      {showCreate && <CreateUserModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
