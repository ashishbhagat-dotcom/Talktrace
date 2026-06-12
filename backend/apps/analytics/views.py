from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.conversations.models import ActionItem, Conversation


def _get_date_range(request):
    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    days = int(request.query_params.get("days", 30))

    if not date_from:
        date_from = (timezone.now() - timedelta(days=days)).date()
    if not date_to:
        date_to = timezone.now().date()

    return date_from, date_to


class AnalyticsSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        date_from, date_to = _get_date_range(request)
        conversations = Conversation.objects.filter(is_deleted=False)

        # Members only see their own stats; admins and managers see all
        if request.user.role == "member":
            conversations = conversations.filter(created_by=request.user)

        period_convs = conversations.filter(
            interaction_date__date__gte=date_from,
            interaction_date__date__lte=date_to,
        )

        total = period_convs.count()
        avg_sentiment = period_convs.aggregate(avg=Avg("sentiment_score"))["avg"] or 0

        action_qs = ActionItem.objects.filter(conversation__is_deleted=False)
        if request.user.role == "member":
            action_qs = action_qs.filter(conversation__created_by=request.user)

        pending_actions = action_qs.filter(status="pending").count()
        overdue_actions = action_qs.filter(
            status="pending",
            due_date__lt=timezone.now().date(),
        ).count()
        active_customers = period_convs.values("customer").distinct().count()

        return Response({
            "total_conversations": total,
            "avg_sentiment_score": round(avg_sentiment, 2),
            "pending_actions": pending_actions,
            "overdue_actions": overdue_actions,
            "active_customers": active_customers,
            "date_from": str(date_from),
            "date_to": str(date_to),
        })


class VolumeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        date_from, date_to = _get_date_range(request)
        group_by = request.query_params.get("group_by", "day")

        trunc_fn = {"day": TruncDate, "week": TruncWeek, "month": TruncMonth}.get(
            group_by, TruncDate
        )

        data = (
            Conversation.objects.filter(
                is_deleted=False,
                interaction_date__date__gte=date_from,
                interaction_date__date__lte=date_to,
            )
            .annotate(period=trunc_fn("interaction_date"))
            .values("period")
            .annotate(count=Count("id"))
            .order_by("period")
        )

        return Response([
            {"date": str(item["period"]), "count": item["count"]}
            for item in data
        ])


class SentimentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        date_from, date_to = _get_date_range(request)

        distribution = (
            Conversation.objects.filter(
                is_deleted=False,
                interaction_date__date__gte=date_from,
                interaction_date__date__lte=date_to,
                sentiment__isnull=False,
            )
            .values("sentiment")
            .annotate(count=Count("id"))
            .order_by("sentiment")
        )

        trend = (
            Conversation.objects.filter(
                is_deleted=False,
                interaction_date__date__gte=date_from,
                interaction_date__date__lte=date_to,
            )
            .annotate(date=TruncDate("interaction_date"))
            .values("date")
            .annotate(avg_score=Avg("sentiment_score"))
            .order_by("date")
        )

        return Response({
            "distribution": list(distribution),
            "trend": [
                {"date": str(item["date"]), "avg_score": round(item["avg_score"] or 0, 2)}
                for item in trend
            ],
        })


class TeamActivityView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        date_from, date_to = _get_date_range(request)

        data = (
            Conversation.objects.filter(
                is_deleted=False,
                interaction_date__date__gte=date_from,
                interaction_date__date__lte=date_to,
                created_by__isnull=False,
            )
            .values("created_by__id", "created_by__name")
            .annotate(count=Count("id"), avg_sentiment=Avg("sentiment_score"))
            .order_by("-count")
        )

        return Response([
            {
                "user_id": str(item["created_by__id"]),
                "user_name": item["created_by__name"],
                "conversations": item["count"],
                "avg_sentiment": round(item["avg_sentiment"] or 0, 2),
            }
            for item in data
        ])


class TopicsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        date_from, date_to = _get_date_range(request)

        conversations = Conversation.objects.filter(
            is_deleted=False,
            interaction_date__date__gte=date_from,
            interaction_date__date__lte=date_to,
        ).values_list("topics", flat=True)

        from collections import Counter
        all_topics = []
        for topics in conversations:
            all_topics.extend(topics or [])

        topic_counts = Counter(all_topics).most_common(20)
        return Response([{"topic": t, "count": c} for t, c in topic_counts])


class CompetitorsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        date_from, date_to = _get_date_range(request)

        conversations = Conversation.objects.filter(
            is_deleted=False,
            interaction_date__date__gte=date_from,
            interaction_date__date__lte=date_to,
        ).values_list("competitor_mentions", flat=True)

        from collections import Counter
        all_competitors = []
        for competitors in conversations:
            all_competitors.extend(competitors or [])

        competitor_counts = Counter(all_competitors).most_common(15)
        return Response([{"competitor": c, "count": n} for c, n in competitor_counts])


class FollowUpsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        date_from, date_to = _get_date_range(request)

        items = ActionItem.objects.filter(
            conversation__is_deleted=False,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )

        total = items.count()
        by_status = items.values("status").annotate(count=Count("id"))

        status_map = {item["status"]: item["count"] for item in by_status}

        completed = status_map.get("completed", 0)
        pending = status_map.get("pending", 0)
        in_progress = status_map.get("in_progress", 0)
        cancelled = status_map.get("cancelled", 0)
        overdue = items.filter(
            status__in=["pending", "in_progress"],
            due_date__lt=timezone.now().date(),
        ).count()

        return Response({
            "total": total,
            "completed": completed,
            "pending": pending,
            "in_progress": in_progress,
            "cancelled": cancelled,
            "overdue": overdue,
            "completion_rate": round(completed / total * 100, 1) if total else 0,
        })
