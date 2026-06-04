import { useEffect, useState } from "react";
import { CheckCircle, Loader2, XCircle } from "lucide-react";
import { getConversationStatus } from "../../api/conversations";

const STEPS = [
  { key: "transcribing", label: "Transcribing audio..." },
  { key: "analyzing", label: "Analyzing conversation..." },
  { key: "summarizing", label: "Generating AI summary..." },
  { key: "indexing", label: "Building search index..." },
];

export default function AIProcessingStatus({ conversationId, hasAudio }) {
  const [status, setStatus] = useState("pending");
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const { data } = await getConversationStatus(conversationId);
        if (cancelled) return;
        setStatus(data.ai_status);
        if (data.ai_status === "processing") {
          setCurrentStep((s) => Math.min(s + 1, STEPS.length - 1));
        }
      } catch {
        // parent query will handle refetching
      }
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [conversationId]);

  const steps = hasAudio ? STEPS : STEPS.slice(1);

  return (
    <div className="card p-6 mb-6">
      <h3 className="font-semibold text-slate-800 mb-4">
        {status === "failed" ? "AI Processing Failed" : "AI is analyzing your conversation..."}
      </h3>

      {status === "failed" ? (
        <div className="flex items-center gap-2 text-red-600">
          <XCircle size={18} />
          <span className="text-sm">Processing failed. Please try again.</span>
        </div>
      ) : (
        <div className="space-y-3">
          {steps.map((step, i) => {
            const isDone = i < currentStep;
            const isActive = i === currentStep;
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
