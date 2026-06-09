import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Phone, Users, Video, MessageCircle, Mail, MoreHorizontal, Search, ChevronLeft } from "lucide-react";
import toast from "react-hot-toast";
import { createConversation, uploadVoice } from "../api/conversations";
import { getGmailStatus, searchGmailThreads, getGmailThread, importGmailThread } from "../api/integrations";
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

  // Gmail state
  const [threadSearch, setThreadSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedThread, setSelectedThread] = useState(null);
  const debounceTimer = useRef(null);

  const { data: gmailStatusRes } = useQuery({
    queryKey: ["gmail-status"],
    queryFn: () => getGmailStatus().then((r) => r.data),
    retry: false,
  });
  const gmailConnected = gmailStatusRes?.connected ?? false;

  // Debounce the search input
  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(threadSearch);
    }, 500);
    return () => clearTimeout(debounceTimer.current);
  }, [threadSearch]);

  // When convType changes to/from "email", adjust the active tab
  useEffect(() => {
    if (convType === "email") {
      if (gmailConnected) {
        setActiveTab("gmail");
      } else {
        setActiveTab("text");
      }
    } else {
      if (activeTab === "gmail") setActiveTab("text");
    }
  }, [convType]); // eslint-disable-line react-hooks/exhaustive-deps

  // Pre-fill search with customer email when gmail tab is active
  useEffect(() => {
    if (activeTab === "gmail" && customer?.email && !threadSearch) {
      setThreadSearch(customer.email);
    }
  }, [activeTab, customer]); // eslint-disable-line react-hooks/exhaustive-deps

  const searchParams = {};
  if (debouncedSearch) searchParams.q = debouncedSearch;
  if (customer?.email) searchParams.customer_email = customer.email;

  const { data: threadsRes, isFetching: threadsFetching } = useQuery({
    queryKey: ["gmail-threads", debouncedSearch, customer?.email],
    queryFn: () => searchGmailThreads(searchParams).then((r) => r.data),
    enabled: gmailConnected && activeTab === "gmail",
    retry: false,
  });
  const threads = threadsRes?.threads ?? [];

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!customer) { toast.error("Please select a customer"); return; }

    if (activeTab === "gmail") {
      if (!selectedThread) { toast.error("Please select a Gmail thread"); return; }
    } else if (activeTab === "text" && !rawText.trim()) {
      toast.error("Please enter conversation notes"); return;
    } else if (activeTab === "voice" && !audioBlob) {
      toast.error("Please record audio first"); return;
    }

    setLoading(true);
    try {
      let conversation;

      if (activeTab === "gmail") {
        const { data } = await importGmailThread({
          thread_id: selectedThread.id,
          customer_id: customer.id,
          conversation_type: "email",
          interaction_date: new Date(interactionDate).toISOString(),
        });
        conversation = data;
      } else if (activeTab === "voice") {
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

  // Determine which tabs to show in Step 3
  const tabs = convType === "email" && gmailConnected
    ? ["text", "voice", "gmail"]
    : ["text", "voice"];

  const tabLabels = { text: "Text Notes", voice: "Voice Recording", gmail: "Gmail Thread" };

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
          {convType === "email" && !gmailConnected && (
            <p className="text-xs text-slate-400 mb-3">
              Connect Gmail in Settings to import threads directly.
            </p>
          )}
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
            {tabs.map((tab) => (
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
                {tabLabels[tab]}
              </button>
            ))}
          </div>

          {activeTab === "text" && (
            <textarea
              className="input resize-none"
              rows={8}
              placeholder="Write what was discussed — requirements, pain points, next steps, pricing, anything relevant. AI will extract and structure this for you."
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
          )}

          {activeTab === "voice" && (
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

          {activeTab === "gmail" && (
            <div>
              {selectedThread ? (
                <div>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-3">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <p className="font-medium text-slate-800 text-sm leading-snug">
                        {selectedThread.subject || "(No subject)"}
                      </p>
                      {selectedThread.message_count && (
                        <span className="shrink-0 text-xs text-slate-500 bg-slate-200 px-2 py-0.5 rounded-full">
                          {selectedThread.message_count} messages
                        </span>
                      )}
                    </div>
                    {selectedThread.raw_text && (
                      <p className="text-xs text-slate-500 leading-relaxed line-clamp-4">
                        {selectedThread.raw_text.slice(0, 300)}
                        {selectedThread.raw_text.length > 300 && "…"}
                      </p>
                    )}
                    {selectedThread.date && (
                      <p className="text-xs text-slate-400 mt-2">{selectedThread.date}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedThread(null)}
                    className="btn-secondary flex items-center gap-1.5 text-sm"
                  >
                    <ChevronLeft size={14} />
                    Change thread
                  </button>
                </div>
              ) : (
                <div>
                  <div className="relative mb-3">
                    <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                    <input
                      type="text"
                      className="input pl-9"
                      placeholder="Search threads by subject or keyword…"
                      value={threadSearch}
                      onChange={(e) => setThreadSearch(e.target.value)}
                    />
                  </div>

                  {threadsFetching && (
                    <div className="flex items-center justify-center py-8 text-slate-400">
                      <Loader2 size={18} className="animate-spin mr-2" />
                      <span className="text-sm">Searching…</span>
                    </div>
                  )}

                  {!threadsFetching && threads.length === 0 && debouncedSearch && (
                    <p className="text-sm text-slate-400 text-center py-6">No threads found.</p>
                  )}

                  {!threadsFetching && threads.length === 0 && !debouncedSearch && (
                    <p className="text-sm text-slate-400 text-center py-6">
                      Search for an email thread above to get started.
                    </p>
                  )}

                  {!threadsFetching && threads.length > 0 && (
                    <ul className="border border-slate-200 rounded-lg divide-y divide-slate-100 overflow-hidden">
                      {threads.map((thread) => (
                        <li key={thread.id}>
                          <button
                            type="button"
                            onClick={async () => {
                              try {
                                const { data } = await getGmailThread(thread.id);
                                setSelectedThread(data);
                              } catch {
                                // Fallback to snippet data if detail fetch fails
                                setSelectedThread({ id: thread.id, subject: thread.snippet, raw_text: "" });
                              }
                            }}
                            className="w-full text-left px-4 py-3 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                          >
                            <p className="font-medium text-slate-800 truncate">
                              {thread.snippet || "(No subject)"}
                            </p>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
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
