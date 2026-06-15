import { useState, useRef, useEffect } from "react";
import RecordRTC from "recordrtc";
import { Mic, Square, AlertCircle } from "lucide-react";

export default function AudioRecorder({ onRecordingComplete }) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState(null);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    return () => {
      clearInterval(timerRef.current);
      stopStream();
    };
  }, []);

  const stopStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  };

  const startRecording = async () => {
    setError(null);

    if (!window.isSecureContext || !navigator.mediaDevices) {
      setError(
        "Microphone access requires a secure connection (HTTPS). Please open the app using https:// instead of http://."
      );
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;

      const recorder = new RecordRTC(stream, {
        type: "audio",
        mimeType: "audio/wav",
        recorderType: RecordRTC.StereoAudioRecorder,
        sampleRate: 16000,
        desiredSampRate: 16000,
        numberOfAudioChannels: 1,
        timeSlice: 1000,
      });

      recorderRef.current = recorder;
      recorder.startRecording();

      setRecording(true);
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (err) {
      setError(
        err.name === "NotAllowedError"
          ? "Microphone access denied. Please allow microphone access in your browser."
          : "Could not start recording. Please check your microphone."
      );
    }
  };

  const stopRecording = () => {
    if (!recorderRef.current || !recording) return;

    recorderRef.current.stopRecording(() => {
      const blob = recorderRef.current.getBlob();
      onRecordingComplete(blob, "audio/wav");
      recorderRef.current = null;
      stopStream();
    });

    setRecording(false);
    clearInterval(timerRef.current);
  };

  const formatTime = (s) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="flex flex-col items-center gap-4 py-8">
      {error && (
        <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-4 py-3 w-full">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {recording && (
        <div className="flex flex-col items-center gap-2">
          <div className="w-4 h-4 bg-red-500 rounded-full animate-pulse" />
          <span className="text-2xl font-mono font-semibold text-slate-800">
            {formatTime(seconds)}
          </span>
          <span className="text-sm text-slate-500">Recording...</span>
        </div>
      )}

      <button
        type="button"
        onClick={recording ? stopRecording : startRecording}
        className={`w-16 h-16 rounded-full flex items-center justify-center transition-colors ${
          recording
            ? "bg-red-500 hover:bg-red-600 text-white"
            : "bg-brand-600 hover:bg-brand-700 text-white"
        }`}
      >
        {recording ? <Square size={24} /> : <Mic size={24} />}
      </button>

      <p className="text-sm text-slate-500">
        {recording ? "Click to stop recording" : "Click to start recording"}
      </p>
    </div>
  );
}
