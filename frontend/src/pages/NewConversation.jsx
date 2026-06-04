import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Phone, Users, Video, MessageCircle, Mail, MoreHorizontal } from "lucide-react";
import toast from "react-hot-toast";
import { createConversation, uploadVoice } from "../api/conversations";
import CustomerSearch from "../components/customers/CustomerSearch";
import AudioRecorder from "../components/conversations/AudioRecorder";

const TYPES = [
  { value: "phone_call", label: "Phone Call", icon: Phone },
  { value: "in_person", label: "In Person", icon: Users },
  { value: "video_call", label: "Video Call", icon: Video },
  { value: "whatsapp", label: "WhatsApp", icon: MessageCircle },
  { value: "email", label: "Email", icon: Mail },
  { value: "other", label: "Other", icon: MoreHorizontal },
];

export default function NewConversation() {
  const navigate = useNavigate();
  const [customer, setCustomer] = useState(null);
  const [convType, setConvType] = useState("phone_call");
  const [interactionDate, setInteractionDate] = useState(
    new Date().toISOString().slice(0, 16)
  );
  const [activeTab, setActiveTab] = useState("text");
  const [rawText, setRawText] = useState("");
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioMime, setAudioMime] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!customer) { toast.error("Please select a customer"); return; }
    if (activeTab === "text" && !rawText.trim()) { toast.error("Please enter conversation notes"); return; }
    if (activeTab === "voice" && !audioBlob) { toast.error("Please record audio first"); return; }

    setLoading(true);
    try {
      let conversation;

      if (activeTab === "voice") {
        const formData = new FormData();
        const ext = audioMime?.includes("webm") ? "webm" : "ogg";
        formData.append("audio", audioBlob, `recording.${ext}`);
        formData.append("customer_id", customer.id);
        formData.append("conversation_type", convType);
        formData.append("interaction_date", new Date(interactionDate).toISOString());

        const { data } = await uploadVoice(formData, (e) => {
          setUploadProgress(Math.round((e.loaded * 100) / e.total));
        });
        conversation = data;
      } else {
        const { data } = await createConversation({
          customer_id: customer.id,
          conversation_type: convType,
          raw_text: rawText,
          interaction_date: new Date(interactionDate).toISOString(),
        });
        conversation = data;
      }

      toast.success("Conversation saved! AI is analyzing...");
      navigate(`/conversations/${conversation.id}`);
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to save conversation");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">New Conversation</h1>
        <p className="text-slate-500 mt-1">Capture a conversation and let AI extract the insights.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Step 1: Customer */}
        <div className="card p-6">
          <h2 className="font-semibold text-slate-800 mb-4">1. Select Customer</h2>
          <CustomerSearch value={customer} onChange={setCustomer} placeholder="Search by name, email, or company..." />
          {customer && (
            <div className="mt-2 text-sm text-slate-600 bg-slate-50 rounded-lg px-3 py-2">
              Selected: <strong>{customer.name}</strong>
              {customer.company && ` · ${customer.company}`}
            </div>
          )}
        </div>

        {/* Step 2: Type + Date */}
        <div className="card p-6">
          <h2 className="font-semibold text-slate-800 mb-4">2. Conversation Details</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-4">
            {TYPES.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => setConvType(value)}
                className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm font-medium transition-colors ${
                  convType === value
                    ? "border-brand-500 bg-brand-50 text-brand-700"
                    : "border-slate-200 text-slate-600 hover:border-slate-300"
                }`}
              >
                <Icon size={15} />
                {label}
              </button>
            ))}
          </div>
          <div>
            <label className="label">When did this happen?</label>
            <input
              type="datetime-local"
              className="input"
              value={interactionDate}
              onChange={(e) => setInteractionDate(e.target.value)}
            />
          </div>
        </div>

        {/* Step 3: Content */}
        <div className="card p-6">
          <h2 className="font-semibold text-slate-800 mb-4">3. Conversation Content</h2>

          <div className="flex border-b border-slate-200 mb-4">
            {["text", "voice"].map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
                  activeTab === tab
                    ? "border-brand-500 text-brand-600"
                    : "border-transparent text-slate-500 hover:text-slate-700"
                }`}
              >
                {tab} {tab === "voice" ? "Recording" : "Notes"}
              </button>
            ))}
          </div>

          {activeTab === "text" ? (
            <textarea
              className="input resize-none"
              rows={8}
              placeholder="Write what was discussed — requirements, pain points, next steps, pricing, anything relevant. AI will extract and structure this for you."
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
          ) : (
            <div>
              <AudioRecorder
                onRecordingComplete={(blob, mime) => {
                  setAudioBlob(blob);
                  setAudioMime(mime);
                }}
              />
              {audioBlob && (
                <div className="mt-3 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                  Recording ready ({(audioBlob.size / 1024).toFixed(1)} KB) — click Submit to upload
                </div>
              )}
              {uploadProgress > 0 && uploadProgress < 100 && (
                <div className="mt-3">
                  <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-brand-500 transition-all"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                  <p className="text-xs text-slate-500 mt-1">Uploading... {uploadProgress}%</p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3">
          <button type="button" onClick={() => navigate(-1)} className="btn-secondary">
            Cancel
          </button>
          <button type="submit" disabled={loading} className="btn-primary">
            {loading && <Loader2 size={16} className="animate-spin" />}
            {loading ? "Saving..." : "Save & Analyze"}
          </button>
        </div>
      </form>
    </div>
  );
}
