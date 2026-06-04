import logging

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.conversations.models import Conversation
from apps.conversations.serializers import ConversationListSerializer
from common.pagination import StandardResultsPagination

logger = logging.getLogger(__name__)


class SearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        mode = request.query_params.get("mode", "hybrid")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))

        filters = {
            "customer": request.query_params.get("customer"),
            "sentiment": request.query_params.getlist("sentiment"),
            "conversation_type": request.query_params.get("type"),
            "created_by": request.query_params.get("created_by"),
            "date_from": request.query_params.get("date_from"),
            "date_to": request.query_params.get("date_to"),
            "topics": request.query_params.getlist("topics"),
        }
        # Remove empty filters
        filters = {k: v for k, v in filters.items() if v}

        if not query:
            qs = Conversation.objects.filter(is_deleted=False).select_related(
                "customer", "created_by"
            ).order_by("-interaction_date")
            paginator = StandardResultsPagination()
            page_qs = paginator.paginate_queryset(qs, request)
            serializer = ConversationListSerializer(page_qs, many=True)
            return paginator.get_paginated_response(serializer.data)

        try:
            if mode == "keyword":
                from apps.conversations.services.search_service import keyword_search
                results = keyword_search(query, filters, page, page_size)
                ids = [hit["_source"]["conversation_id"] for hit in results.get("hits", {}).get("hits", [])]
                total = results.get("hits", {}).get("total", {}).get("value", 0)
                conversations = {
                    str(c.id): c
                    for c in Conversation.objects.filter(id__in=ids).select_related("customer", "created_by")
                }
                ordered = [conversations[cid] for cid in ids if cid in conversations]
                serializer = ConversationListSerializer(ordered, many=True)
                return Response({
                    "count": total,
                    "mode": mode,
                    "results": serializer.data,
                })

            elif mode == "semantic":
                from apps.conversations.services.search_service import semantic_search
                conversations = list(semantic_search(query, filters, page, page_size))
                serializer = ConversationListSerializer(conversations, many=True)
                return Response({
                    "count": len(conversations),
                    "mode": mode,
                    "results": serializer.data,
                })

            else:  # hybrid (default)
                from apps.conversations.services.search_service import hybrid_search
                conversations, scores = hybrid_search(query, filters, page, page_size)
                serializer = ConversationListSerializer(conversations, many=True)
                return Response({
                    "count": len(scores),
                    "mode": mode,
                    "results": serializer.data,
                })

        except Exception as e:
            logger.error(f"Search error: {e}")
            return Response({"error": "Search service unavailable", "results": []}, status=503)


class SearchFiltersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.conversations.services.search_service import get_es_client, CONVERSATIONS_INDEX
        from elasticsearch import NotFoundError

        try:
            es = get_es_client()
            agg_body = {
                "size": 0,
                "aggs": {
                    "sentiments": {"terms": {"field": "sentiment", "size": 10}},
                    "types": {"terms": {"field": "conversation_type", "size": 10}},
                    "topics": {"terms": {"field": "topics", "size": 30}},
                    "competitors": {"terms": {"field": "competitor_mentions", "size": 20}},
                },
            }
            result = es.search(index=CONVERSATIONS_INDEX, body=agg_body)
            aggs = result.get("aggregations", {})
            return Response({
                "sentiments": [b["key"] for b in aggs.get("sentiments", {}).get("buckets", [])],
                "types": [b["key"] for b in aggs.get("types", {}).get("buckets", [])],
                "topics": [b["key"] for b in aggs.get("topics", {}).get("buckets", [])],
                "competitors": [b["key"] for b in aggs.get("competitors", {}).get("buckets", [])],
            })
        except Exception:
            # Fallback to DB if ES is down
            from django.db.models import Count
            topics = (
                Conversation.objects.filter(is_deleted=False)
                .values_list("topics", flat=True)
            )
            all_topics = []
            for t in topics:
                all_topics.extend(t or [])
            from collections import Counter
            top_topics = [t for t, _ in Counter(all_topics).most_common(30)]
            return Response({
                "sentiments": [c[0] for c in Conversation.Sentiment.choices],
                "types": [c[0] for c in Conversation.Type.choices],
                "topics": top_topics,
                "competitors": [],
            })
