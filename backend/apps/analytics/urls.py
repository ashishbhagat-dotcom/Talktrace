from django.urls import path
from .views import (
    AnalyticsSummaryView,
    CompetitorsView,
    FollowUpsView,
    SentimentView,
    TeamActivityView,
    TopicsView,
    VolumeView,
)

urlpatterns = [
    path("analytics/summary/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("analytics/volume/", VolumeView.as_view(), name="analytics-volume"),
    path("analytics/sentiment/", SentimentView.as_view(), name="analytics-sentiment"),
    path("analytics/team/", TeamActivityView.as_view(), name="analytics-team"),
    path("analytics/topics/", TopicsView.as_view(), name="analytics-topics"),
    path("analytics/competitors/", CompetitorsView.as_view(), name="analytics-competitors"),
    path("analytics/follow-ups/", FollowUpsView.as_view(), name="analytics-followups"),
]
