import client from "./client";

export const getActionItems = (params) =>
  client.get("/action-items/", { params });

export const getMyActionItems = (params) =>
  client.get("/action-items/my/", { params });

export const getOverdueActionItems = () => client.get("/action-items/overdue/");

export const updateActionItem = (id, data) =>
  client.patch(`/action-items/${id}/`, data);
