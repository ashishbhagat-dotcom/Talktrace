from django.db.models import Count, Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from common.pagination import StandardResultsPagination
from .models import Customer
from .serializers import CustomerSerializer, CustomerAutocompleteSerializer


class CustomerViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        qs = Customer.objects.annotate(conversation_count=Count("conversations"))
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(email__icontains=q) | Q(company__icontains=q)
            )
        customer_type = self.request.query_params.get("type")
        if customer_type:
            qs = qs.filter(type=customer_type)
        return qs

    def get_serializer_class(self):
        return CustomerSerializer

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response([])
        customers = Customer.objects.filter(
            Q(name__icontains=q) | Q(email__icontains=q) | Q(company__icontains=q)
        )[:10]
        return Response(CustomerAutocompleteSerializer(customers, many=True).data)

    @action(detail=True, methods=["get"], url_path="timeline")
    def timeline(self, request, pk=None):
        from apps.conversations.models import Conversation
        from apps.conversations.serializers import ConversationListSerializer

        customer = self.get_object()
        conversations = (
            Conversation.objects.filter(customer=customer, is_deleted=False)
            .select_related("created_by")
            .order_by("-interaction_date")
        )
        page = self.paginate_queryset(conversations)
        if page is not None:
            return self.get_paginated_response(
                ConversationListSerializer(page, many=True).data
            )
        return Response(ConversationListSerializer(conversations, many=True).data)
