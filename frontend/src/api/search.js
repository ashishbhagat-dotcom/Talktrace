import client from "./client";

export const search = (params) => client.get("/search/", { params });

export const getSearchFilters = () => client.get("/search/filters/");
