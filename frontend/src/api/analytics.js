import client from "./client";

export const getSummary = (params) =>
  client.get("/analytics/summary/", { params });

export const getVolume = (params) =>
  client.get("/analytics/volume/", { params });

export const getSentiment = (params) =>
  client.get("/analytics/sentiment/", { params });

export const getTeamActivity = (params) =>
  client.get("/analytics/team/", { params });

export const getTopics = (params) =>
  client.get("/analytics/topics/", { params });

export const getCompetitors = (params) =>
  client.get("/analytics/competitors/", { params });

export const getFollowUps = (params) =>
  client.get("/analytics/follow-ups/", { params });
