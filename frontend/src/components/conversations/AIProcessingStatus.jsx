import { useEffect, useRef, useState } from "react";
import { CheckCircle, Loader2, XCircle } from "lucide-react";
import { getConversationStatus } from "../../api/conversations";

const STEPS = [
  { key: "transcribing", label: "Transcribing audio..." },
  { key: "analyzing", label: "Analyzing conversation..." },
  { key: "summarizing", label: "Generating AI summary..." },
  { key: "indexing", label: "Building search index..." },
  { key: "preparing", label: "Preparing results..." },
];

// How long to keep each non-final processing step "active" before
// progressing visually. The backend gives us only a binary
// "transcribing" / "processing" / "ready_for_review" signal, so we
// pace the visual steps internally with a slow timer instead of
// flashing through them in a couple of seconds.
const STEP_DWELL_MS = 8000;

export default function AIProcessingStatus({ conversationId, hasAudio }) {
  const [status, setStatus] = useState("pending");
  const [currentStep, setCurrentStep] = useState(hasAudio ? 0 : 1);
  const processingStartRef = useRef(null); // timestamp when status entered "processing"

  // Poll backend for the real status. We never advance steps based on poll
  // count — only on the wall-clock dwell timer below.
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const { data } = await getConversationStatus(conversationId);
        if (cancelled) return;
        setStatus(data.ai_status);

        if (data.ai_status === "transcribing" || data.ai_status === "pending") {
          // Only "Transcribing audio" is active during the transcription phase
          setCurrentStep(0);
          processingStartRef.current = null;
        } else if (data.ai_status === "processing") {
          // First time we see "processing", remember when. The dwell timer
          // will then advance visual steps from "Analyzing" onward.
          if (processingStartRef.current == null) {
            processingStartRef.current = Date.now();
            // If we have audio, the user already saw the transcript-review
            // screen, so "Transcribing" is conceptually already past — jump
            // straight to "Analyzing" (index 1). For text-only, start at 1 too
            // since "Transcribing" doesn't apply.
            setCurrentStep(1);
          }
        }
      } catch {
        // ignore; parent query covers retries
      }
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [conversationId, hasAudio]);

  // Dwell timer: while we're in "processing", advance the visual step every
  // STEP_DWELL_MS, capped at the second-to-last step (the final
  // "Preparing results..." step stays spinning until the parent unmounts us).
  useEffect(() => {
    if (status !== "processing") return;
    const tick = setInterval(() => {
      setCurrentStep((s) => Math.min(s + 1, STEPS.length - 2));
    }, STEP_DWELL_MS);
    return () => clearInterval(tick);
  }, [status]);

  const steps = hasAudio ? STEPS : STEPS.slice(1);
  // Adjust currentStep index when we hide the Transcribing row for text-only
  const displayedCurrent = hasAudio ? currentStep : Math.max(currentStep - 1, 0);

  return (
    <div className="card p-6 mb-6">
      <h3 className="font-semibold text-slate-800 mb-4">
        {status === "failed"
          ? "AI Processing Failed"
          : status === "transcribing" || status === "pending"
          ? "Transcribing audio..."
          : "AI is analyzing your conversation..."}
      </h3>

      {status === "failed" ? (
        <div className="flex items-center gap-2 text-red-600">
          <XCircle size={18} />
          <span className="text-sm">Processing failed. Please try again.</span>
        </div>
      ) : (
        <div className="space-y-3">
          {steps.map((step, i) => {
            const isDone = i < displayedCurrent;
            const isActive = i === displayedCurrent;
            return (
              <div key={step.key} className="flex items-center gap-3">
                {isDone ? (
                  <CheckCircle size={18} className="text-green-500 flex-shrink-0" />
                ) : isActive ? (
                  <Loader2 size={18} className="text-brand-500 animate-spin flex-shrink-0" />
                ) : (
                  <div className="w-[18px] h-[18px] rounded-full border-2 border-slate-200 flex-shrink-0" />
                )}
                <span
                  className={`text-sm ${
                    isDone ? "text-slate-400 line-through" : isActive ? "text-slate-800 font-medium" : "text-slate-400"
                  }`}
                >
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
