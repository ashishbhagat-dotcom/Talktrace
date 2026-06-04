import django_filters
from django.utils import timezone
from .models import Conversation, ActionItem


class ConversationFilter(django_filters.FilterSet):
    customer = django_filters.UUIDFilter(field_name="customer__id")
    type = django_filters.ChoiceFilter(
        field_name="conversation_type", choices=Conversation.Type.choices
    )
    sentiment = django_filters.MultipleChoiceFilter(
        field_name="sentiment", choices=Conversation.Sentiment.choices
    )
    ai_status = django_filters.ChoiceFilter(choices=Conversation.AIStatus.choices)
    created_by = django_filters.UUIDFilter(field_name="created_by__id")
    date_from = django_filters.DateFilter(field_name="interaction_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="interaction_date", lookup_expr="lte")
    has_pending_actions = django_filters.BooleanFilter(method="filter_has_pending_actions")

    def filter_has_pending_actions(self, queryset, name, value):
        if value:
            return queryset.filter(action_items__status="pending").distinct()
        return queryset

    class Meta:
        model = Conversation
        fields = ["customer", "type", "sentiment", "ai_status", "created_by"]


class ActionItemFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=ActionItem.Status.choices)
    priority = django_filters.MultipleChoiceFilter(choices=ActionItem.Priority.choices)
    assigned_to = django_filters.UUIDFilter(field_name="assigned_to__id")
    due_from = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_to = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    overdue = django_filters.BooleanFilter(method="filter_overdue")

    def filter_overdue(self, queryset, name, value):
        if value:
            return queryset.filter(
                due_date__lt=timezone.now().date()
            ).exclude(status__in=["completed", "cancelled"])
        return queryset

    class Meta:
        model = ActionItem
        fields = ["status", "priority", "assigned_to"]
