import client from "./client";

export const getUsers = () => client.get("/auth/users/?page_size=100");
export const createUser = (data) => client.post("/auth/users/", data);
export const updateUser = (id, data) => client.patch(`/auth/users/${id}/`, data);
export const deactivateUser = (id) => client.delete(`/auth/users/${id}/`);
export const activateUser = (id) => client.post(`/auth/users/${id}/activate/`);
