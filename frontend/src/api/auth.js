import client from "./client";

export const login = (email, password) =>
  client.post("/auth/login/", { email, password });

export const register = (data) => client.post("/auth/register/", data);

export const refreshToken = (refresh) =>
  client.post("/auth/token/refresh/", { refresh });

export const getMe = () => client.get("/auth/me/");

export const updateProfile = (data) => client.patch("/auth/me/", data);
