import { format, formatDistanceToNow, parseISO } from "date-fns";

export const formatDate = (dateStr) => {
  if (!dateStr) return "—";
  try {
    return format(parseISO(dateStr), "MMM d, yyyy");
  } catch {
    return dateStr;
  }
};

export const formatDateTime = (dateStr) => {
  if (!dateStr) return "—";
  try {
    return format(parseISO(dateStr), "MMM d, yyyy 'at' h:mm a");
  } catch {
    return dateStr;
  }
};

export const timeAgo = (dateStr) => {
  if (!dateStr) return "—";
  try {
    return formatDistanceToNow(parseISO(dateStr), { addSuffix: true });
  } catch {
    return dateStr;
  }
};

export const sentimentLabel = (sentiment) => {
  const map = {
    very_negative: "Very Negative",
    negative: "Negative",
    neutral: "Neutral",
    positive: "Positive",
    very_positive: "Very Positive",
  };
  return map[sentiment] || sentiment;
};

export const conversationTypeLabel = (type) => {
  const map = {
    phone_call: "Phone Call",
    in_person: "In Person",
    video_call: "Video Call",
    whatsapp: "WhatsApp",
    email: "Email",
    other: "Other",
  };
  return map[type] || type;
};

export const truncate = (str, n = 100) =>
  str && str.length > n ? str.slice(0, n) + "..." : str;
