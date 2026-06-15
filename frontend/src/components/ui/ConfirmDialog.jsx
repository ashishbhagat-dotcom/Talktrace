import { useEffect, useRef } from "react";
import { AlertTriangle, X, Loader2 } from "lucide-react";

/**
 * In-app confirmation dialog. Renders a centered modal with a title, body,
 * and Cancel / Confirm buttons. Close via overlay click, Escape, or X.
 *
 * Usage:
 *   <ConfirmDialog
 *     open={open}
 *     title="Delete draft?"
 *     body="..."
 *     confirmLabel="Delete"
 *     destructive
 *     loading={mutation.isPending}
 *     onConfirm={() => mutation.mutate()}
 *     onClose={() => setOpen(false)}
 *   />
 */
export default function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  loading = false,
  onConfirm,
  onClose,
}) {
  const confirmBtnRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape" && !loading) onClose?.();
      if (e.key === "Enter" && !loading) {
        e.preventDefault();
        onConfirm?.();
      }
    };
    window.addEventListener("keydown", onKey);
    confirmBtnRef.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [open, loading, onClose, onConfirm]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget && !loading) onClose?.();
      }}
    >
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 max-w-md w-full overflow-hidden">
        <div className="flex items-start gap-3 p-5">
          <div
            className={
              "w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 " +
              (destructive ? "bg-red-100" : "bg-amber-100")
            }
          >
            <AlertTriangle size={20} className={destructive ? "text-red-600" : "text-amber-600"} />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-900">{title}</h3>
            {body && <div className="text-sm text-slate-600 mt-1 leading-relaxed">{body}</div>}
          </div>
          {!loading && (
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-700 p-1 -m-1 rounded transition-colors"
              aria-label="Close"
            >
              <X size={18} />
            </button>
          )}
        </div>
        <div className="flex justify-end gap-2 px-5 py-3 bg-slate-50 border-t border-slate-100">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-200 rounded-lg transition-colors disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmBtnRef}
            onClick={onConfirm}
            disabled={loading}
            className={
              "px-4 py-1.5 text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50 " +
              (destructive
                ? "bg-red-600 hover:bg-red-700 text-white"
                : "bg-brand-600 hover:bg-brand-700 text-white")
            }
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
