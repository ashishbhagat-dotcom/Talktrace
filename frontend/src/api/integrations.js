import client from "./client";

export const getZohoStatus = () => client.get("/integrations/zoho/status/");
export const getZohoConnectUrl = () => client.get("/integrations/zoho/connect/");
export const disconnectZoho = () => client.delete("/integrations/zoho/disconnect/");
export const triggerZohoSync = () => client.post("/integrations/zoho/sync/");

export const getGmailStatus = () => client.get("/integrations/gmail/status/");
export const getGmailConnectUrl = () => client.get("/integrations/gmail/connect/");
export const disconnectGmail = () => client.delete("/integrations/gmail/disconnect/");
export const searchGmailThreads = (params) => client.get("/integrations/gmail/threads/", { params });
export const getGmailThread = (threadId) => client.get(`/integrations/gmail/threads/${threadId}/`);
export const importGmailThread = (data) => client.post("/conversations/from-gmail/", data);

// ─── CRM Drafts (Lead/Account from Conversation) ────────────────────────────
export const listCrmDrafts = () => client.get("/crm-drafts/");
export const createCrmDraft = (data) => client.post("/crm-drafts/", data);
export const getCrmDraft = (id) => client.get(`/crm-drafts/${id}/`);
export const updateCrmDraft = (id, patch) => client.patch(`/crm-drafts/${id}/`, patch);
export const deleteCrmDraft = (id) => client.delete(`/crm-drafts/${id}/`);
export const submitCrmDraft = (id) => client.post(`/crm-drafts/${id}/submit/`);
