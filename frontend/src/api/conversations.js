import client from "./client";

export const getConversations = (params) =>
  client.get("/conversations/", { params });

export const getConversation = (id) => client.get(`/conversations/${id}/`);

export const createConversation = (data) => client.post("/conversations/", data);

export const updateConversation = (id, data) =>
  client.patch(`/conversations/${id}/`, data);

export const deleteConversation = (id) => client.delete(`/conversations/${id}/`);

export const getConversationStatus = (id) =>
  client.get(`/conversations/${id}/status/`);

export const uploadVoice = (formData, onUploadProgress) =>
  client.post("/conversations/voice/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress,
  });

export const analyzeConversation = (id, rawText) =>
  client.post(`/conversations/${id}/analyze/`, rawText != null ? { raw_text: rawText } : {});
