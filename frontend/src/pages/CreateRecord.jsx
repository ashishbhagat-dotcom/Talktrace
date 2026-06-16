import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus, Building2, ChevronLeft, Loader2, Mic, Type, FileText, Trash2, Upload, FileAudio } from "lucide-react";

const ACCEPTED_AUDIO = ".mp3,.wav,.m4a,.aac,.ogg,.webm,.flac,audio/*";
const MAX_AUDIO_BYTES = 50 * 1024 * 1024; // 50 MB
import toast from "react-hot-toast";
import { createCrmDraft, listCrmDrafts, deleteCrmDraft } from "../api/integrations";
import AudioRecorder from "../components/conversations/AudioRecorder";
import DraftReview from "../components/crm-drafts/DraftReview";
import ConfirmDialog from "../components/ui/ConfirmDialog";

const RECORD_TYPES = [
  {
    value: "lead",
    label: "Create Lead",
    icon: UserPlus,
    description: "An individual prospect — capture their name, contact info, and what they're looking for.",
  },
  {
    value: "account",
    label: "Create Account",
    icon: Building2,
    description: "A company or organization — capture business details and the opportunity.",
  },
];

export default function CreateRecord() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  // Start in review mode if ?draft=<id> is present (used to resume an existing draft)
  const initialDraftId = searchParams.get("draft");
  const [step, setStep] = useState(initialDraftId ? "review" : "type"); // type | capture | review
  const [recordType, setRecordType] = useState(null);
  const [draftId, setDraftId] = useState(initialDraftId);

  const [inputMode, setInputMode] = useState("text"); // text | voice | upload
  const [rawText, setRawText] = useState("");
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioMime, setAudioMime] = useState(null);
  const [uploadFile, setUploadFile] = useState(null);

  const draftsQuery = useQuery({
    queryKey: ["crm-drafts-list"],
    queryFn: () => listCrmDrafts().then((r) => r.data),
    enabled: step === "type",
  });

  const inProgressDrafts = (draftsQuery.data || []).filter(
    (d) => d.status !== "submitted"
  );

  const [confirmingDelete, setConfirmingDelete] = useState(null); // draft object or null
  const deleteMutation = useMutation({
    mutationFn: (id) => deleteCrmDraft(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crm-drafts-list"] });
      setConfirmingDelete(null);
      toast.success("Draft discarded");
    },
    onError: () => {
      toast.error("Couldn't delete the draft. Please try again.");
    },
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const fd = new FormData();
      fd.append("record_type", recordType);
      if (inputMode === "voice" && audioBlob) {
        const ext = audioMime?.includes("webm") ? "webm" : "wav";
        fd.append("audio", audioBlob, `recording.${ext}`);
      } else if (inputMode === "upload" && uploadFile) {
        fd.append("audio", uploadFile, uploadFile.name);
      } else {
        fd.append("raw_text", rawText.trim());
      }
      const r = await createCrmDraft(fd);
      return r.data;
    },
    onSuccess: (draft) => {
      setDraftId(draft.id);
      setStep("review");
      queryClient.invalidateQueries({ queryKey: ["crm-drafts-list"] });
    },
    onError: (err) => {
      toast.error(err.response?.data?.error || "Failed to create draft");
    },
  });

  const canSubmit = (() => {
    if (inputMode === "text") return rawText.trim().length > 10;
    if (inputMode === "voice") return !!audioBlob;
    if (inputMode === "upload") return !!uploadFile;
    return false;
  })();

  if (step === "review" && draftId) {
    return (
      <DraftReview
        draftId={draftId}
        onDone={() => {
          setSearchParams({});
          queryClient.invalidateQueries({ queryKey: ["crm-drafts-list"] });
          navigate("/");
        }}
        onBack={() => {
          // Always go back to the type-picker so the user sees their draft
          // listed under "Continue a draft" (the draft stays saved server-side).
          setSearchParams({});
          setStep("type");
          setDraftId(null);
          // Clear the capture-form state so a fresh draft starts blank
          setRecordType(null);
          setRawText("");
          setAudioBlob(null);
          setAudioMime(null);
          setUploadFile(null);
          queryClient.invalidateQueries({ queryKey: ["crm-drafts-list"] });
        }}
      />
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => (step === "capture" ? setStep("type") : navigate(-1))}
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-2"
        >
          <ChevronLeft size={16} /> Back
        </button>
        <h1 className="text-2xl font-bold text-slate-800">Create CRM Record</h1>
        <p className="text-slate-500 mt-1">
          {step === "type"
            ? "Pick what you want to create from this conversation."
            : "Add the conversation, and AI will extract the details."}
        </p>
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-2 text-xs">
        <StepBadge active={step === "type"} done={step !== "type"} label="1. Type" />
        <span className="text-slate-300">—</span>
        <StepBadge active={step === "capture"} done={step === "review"} label="2. Conversation" />
        <span className="text-slate-300">—</span>
        <StepBadge active={step === "review"} done={false} label="3. Review & Create" />
      </div>

      {step === "type" && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {RECORD_TYPES.map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.value}
                  onClick={() => {
                    setRecordType(t.value);
                    setStep("capture");
                  }}
                  className="card p-6 text-left hover:border-brand-500 hover:shadow-md transition-all group"
                >
                  <div className="w-12 h-12 rounded-lg bg-brand-50 group-hover:bg-brand-100 flex items-center justify-center mb-4 transition-colors">
                    <Icon size={24} className="text-brand-600" />
                  </div>
                  <h3 className="font-semibold text-slate-800 mb-1">{t.label}</h3>
                  <p className="text-sm text-slate-500">{t.description}</p>
                </button>
              );
            })}
          </div>

          {inProgressDrafts.length > 0 && (
            <DraftsList
              drafts={inProgressDrafts}
              onResume={(id) => {
                setDraftId(id);
                setSearchParams({ draft: id });
                setStep("review");
              }}
              onDelete={(draft) => setConfirmingDelete(draft)}
            />
          )}
        </>
      )}

      <ConfirmDialog
        open={!!confirmingDelete}
        title="Discard this draft?"
        body={
          confirmingDelete && (
            <>
              <p>
                This will permanently delete the draft
                {confirmingDelete.extracted_fields?.Account_Name ||
                [confirmingDelete.extracted_fields?.First_Name, confirmingDelete.extracted_fields?.Last_Name]
                  .filter(Boolean)
                  .join(" ") ? (
                  <>
                    {" "}
                    for{" "}
                    <span className="font-medium text-slate-800">
                      {confirmingDelete.extracted_fields?.Account_Name ||
                        [confirmingDelete.extracted_fields?.First_Name, confirmingDelete.extracted_fields?.Last_Name]
                          .filter(Boolean)
                          .join(" ")}
                    </span>
                  </>
                ) : null}
                .
              </p>
              <p className="mt-2 text-xs text-slate-500">
                The conversation transcript and any edits you made will be lost. Nothing will be sent to Zoho.
              </p>
            </>
          )
        }
        confirmLabel="Delete draft"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => confirmingDelete && deleteMutation.mutate(confirmingDelete.id)}
        onClose={() => setConfirmingDelete(null)}
      />

      {step === "capture" && (
        <div className="card p-6 space-y-4">
          <div className="flex items-center gap-1 mb-2 text-xs text-slate-500">
            Creating a <span className="font-semibold text-brand-700 capitalize">{recordType}</span>
          </div>

          {/* Input mode tabs */}
          <div className="flex gap-1 border-b border-slate-200">
            <ModeTab active={inputMode === "text"} onClick={() => setInputMode("text")} icon={Type} label="Type" />
            <ModeTab active={inputMode === "voice"} onClick={() => setInputMode("voice")} icon={Mic} label="Record" />
            <ModeTab active={inputMode === "upload"} onClick={() => setInputMode("upload")} icon={Upload} label="Upload audio" />
          </div>

          {inputMode === "text" && (
            <div>
              <label className="label">Conversation transcript</label>
              <textarea
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder="Paste or type the conversation here — what the customer said, who they are, what they need..."
                rows={10}
                className="input font-mono text-sm"
              />
              <p className="text-xs text-slate-400 mt-1">{rawText.length} characters</p>
            </div>
          )}

          {inputMode === "voice" && (
            <div>
              <AudioRecorder
                onRecordingComplete={(blob, mime) => {
                  setAudioBlob(blob);
                  setAudioMime(mime);
                }}
              />
              {audioBlob && (
                <p className="text-xs text-green-600 mt-2">
                  ✓ Recording captured ({Math.round(audioBlob.size / 1024)} KB) — will transcribe after submit
                </p>
              )}
            </div>
          )}

          {inputMode === "upload" && (
            <AudioUploadField file={uploadFile} setFile={setUploadFile} />
          )}

          <div className="flex justify-end pt-2">
            <button
              onClick={() => createMutation.mutate()}
              disabled={!canSubmit || createMutation.isPending}
              className="btn-primary flex items-center gap-2"
            >
              {createMutation.isPending && <Loader2 size={15} className="animate-spin" />}
              Analyze with AI
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StepBadge({ active, done, label }) {
  return (
    <span
      className={
        "px-2 py-1 rounded-full " +
        (done
          ? "bg-green-100 text-green-700"
          : active
          ? "bg-brand-100 text-brand-700 font-medium"
          : "bg-slate-100 text-slate-500")
      }
    >
      {label}
    </span>
  );
}

function DraftsList({ drafts, onResume, onDelete }) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-3">
        <FileText size={16} className="text-slate-500" />
        <h3 className="font-semibold text-slate-800">Continue a draft</h3>
        <span className="text-xs text-slate-400">{drafts.length}</span>
      </div>
      <div className="divide-y divide-slate-100">
        {drafts.map((d) => {
          const label = d.record_type === "lead" ? "Lead" : "Account";
          const name =
            d.extracted_fields?.Account_Name ||
            [d.extracted_fields?.First_Name, d.extracted_fields?.Last_Name].filter(Boolean).join(" ") ||
            "Untitled";
          const statusColor =
            d.status === "ready"
              ? "bg-green-100 text-green-700"
              : d.status === "extracting"
              ? "bg-blue-100 text-blue-700"
              : d.status === "failed"
              ? "bg-red-100 text-red-700"
              : "bg-slate-100 text-slate-600";
          return (
            <div key={d.id} className="flex items-center justify-between py-3 gap-3">
              <button
                onClick={() => onResume(d.id)}
                className="flex-1 text-left min-w-0 hover:opacity-80"
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-slate-800 truncate">{name}</span>
                  <span className="text-xs text-slate-400">· {label}</span>
                  <span className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded ${statusColor}`}>
                    {d.status}
                  </span>
                  {d.missing_required?.length > 0 && (
                    <span className="text-[10px] text-amber-700">
                      {d.missing_required.length} required missing
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-0.5 truncate">
                  {d.ai_summary || d.raw_text?.slice(0, 100) || "—"}
                </p>
              </button>
              <button
                onClick={() => onDelete(d)}
                className="text-slate-400 hover:text-red-500 p-1 rounded transition-colors"
                title="Delete draft"
              >
                <Trash2 size={15} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AudioUploadField({ file, setFile }) {
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const accept = (f) => {
    setError(null);
    if (!f) return;
    if (!f.type.startsWith("audio/") && !/\.(mp3|wav|m4a|aac|ogg|webm|flac)$/i.test(f.name)) {
      setError("That doesn't look like an audio file. Supported: MP3, WAV, M4A, AAC, OGG, WebM, FLAC.");
      return;
    }
    if (f.size > MAX_AUDIO_BYTES) {
      setError(`File too large (${Math.round(f.size / 1024 / 1024)} MB). Maximum is 50 MB.`);
      return;
    }
    setFile(f);
  };

  return (
    <div>
      <label className="label">Upload customer conversation audio</label>

      <label
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          accept(e.dataTransfer.files?.[0]);
        }}
        className={
          "flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-xl py-8 px-4 cursor-pointer transition-colors " +
          (dragOver
            ? "border-brand-500 bg-brand-50"
            : "border-slate-300 hover:border-brand-400 hover:bg-slate-50")
        }
      >
        <input
          type="file"
          accept={ACCEPTED_AUDIO}
          onChange={(e) => accept(e.target.files?.[0])}
          className="hidden"
        />
        <FileAudio size={32} className="text-slate-400" />
        <div className="text-center">
          <p className="text-sm text-slate-700 font-medium">
            {file ? file.name : "Drag & drop or click to choose an audio file"}
          </p>
          <p className="text-xs text-slate-500 mt-0.5">
            {file
              ? `${(file.size / 1024 / 1024).toFixed(1)} MB · ${file.type || "audio"}`
              : "MP3, WAV, M4A, AAC, OGG, WebM, FLAC — up to 50 MB"}
          </p>
        </div>
        {file && (
          <button
            type="button"
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); setFile(null); }}
            className="text-xs text-slate-500 hover:text-red-600 underline mt-1"
          >
            Choose a different file
          </button>
        )}
      </label>

      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}

      {file && !error && (
        <p className="text-xs text-green-600 mt-2">
          ✓ Ready. After submit, the audio will be transcribed and analyzed with AI.
        </p>
      )}
    </div>
  );
}

function ModeTab({ active, onClick, icon: Icon, label }) {
  return (
    <button
      onClick={onClick}
      className={
        "flex items-center gap-1.5 px-3 py-2 text-sm transition-colors border-b-2 -mb-px " +
        (active
          ? "border-brand-500 text-brand-700 font-medium"
          : "border-transparent text-slate-500 hover:text-slate-800")
      }
    >
      <Icon size={15} /> {label}
    </button>
  );
}
