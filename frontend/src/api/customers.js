import client from "./client";

export const getCustomers = (params) => client.get("/customers/", { params });

export const getCustomer = (id) => client.get(`/customers/${id}/`);

export const createCustomer = (data) => client.post("/customers/", data);

export const updateCustomer = (id, data) => client.patch(`/customers/${id}/`, data);

export const searchCustomers = (q) =>
  client.get("/customers/search/", { params: { q } });

export const getCustomerTimeline = (id, params) =>
  client.get(`/customers/${id}/timeline/`, { params });
