import client from "./client";

export const getZohoStatus = () => client.get("/integrations/zoho/status/");
export const getZohoConnectUrl = () => client.get("/integrations/zoho/connect/");
export const disconnectZoho = () => client.delete("/integrations/zoho/disconnect/");
export const triggerZohoSync = () => client.post("/integrations/zoho/sync/");
