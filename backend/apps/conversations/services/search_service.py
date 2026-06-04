import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from django.conf import settings
from elasticsearch import Elasticsearch

logger = logging.getLogger(__name__)

CONVERSATIONS_INDEX = f"{settings.ELASTICSEARCH_INDEX_PREFIX}_conversations"

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "conversation_id": {"type": "keyword"},
            "customer_id": {"type": "keyword"},
            "customer_name": {"type": "text", "analyzer": "standard"},
            "customer_company": {"type": "text", "analyzer": "standard"},
            "raw_text": {"type": "text", "analyzer": "english"},
            "ai_summary": {"type": "text", "analyzer": "english"},
            "customer_requirements": {"type": "text", "analyzer": "english"},
            "pain_points": {"type": "text", "analyzer": "english"},
            "next_steps": {"type": "text", "analyzer": "english"},
            "topics": {"type": "keyword"},
            "competitor_mentions": {"type": "keyword"},
            "conversation_type": {"type": "keyword"},
            "sentiment": {"type": "keyword"},
            "sentiment_score": {"type": "float"},
            "interaction_date": {"type": "date"},
            "created_by_id": {"type": "keyword"},
            "created_by_name": {"type": "keyword"},
        }
    }
}


def get_es_client() -> Elasticsearch:
    return Elasticsearch(settings.ELASTICSEARCH_URL)


def ensure_index_exists():
    es = get_es_client()
    if not es.indices.exists(index=CONVERSATIONS_INDEX):
        es.indices.create(index=CONVERSATIONS_INDEX, body=INDEX_MAPPING)
        logger.info(f"Created Elasticsearch index: {CONVERSATIONS_INDEX}")


def index_conversation(conversation) -> bool:
    try:
        es = get_es_client()
        doc = {
            "conversation_id": str(conversation.id),
            "customer_id": str(conversation.customer_id),
            "customer_name": conversation.customer.name,
            "customer_company": conversation.customer.company,
            "raw_text": conversation.raw_text,
            "ai_summary": conversation.ai_summary or "",
            "customer_requirements": conversation.customer_requirements or "",
            "pain_points": conversation.pain_points or "",
            "next_steps": conversation.next_steps or "",
            "topics": conversation.topics,
            "competitor_mentions": conversation.competitor_mentions,
            "conversation_type": conversation.conversation_type,
            "sentiment": conversation.sentiment,
            "sentiment_score": conversation.sentiment_score,
            "interaction_date": conversation.interaction_date.isoformat() if conversation.interaction_date else None,
            "created_by_id": str(conversation.created_by_id) if conversation.created_by_id else None,
            "created_by_name": conversation.created_by.name if conversation.created_by else None,
        }
        es.index(index=CONVERSATIONS_INDEX, id=str(conversation.id), document=doc)
        return True
    except Exception as e:
        logger.error(f"Failed to index conversation {conversation.id}: {e}")
        return False


def _build_es_filters(filters: dict) -> list:
    must = []
    if filters.get("customer"):
        must.append({"term": {"customer_id": str(filters["customer"])}})
    if filters.get("sentiment"):
        must.append({"terms": {"sentiment": filters["sentiment"] if isinstance(filters["sentiment"], list) else [filters["sentiment"]]}})
    if filters.get("conversation_type"):
        must.append({"term": {"conversation_type": filters["conversation_type"]}})
    if filters.get("created_by"):
        must.append({"term": {"created_by_id": str(filters["created_by"])}})
    if filters.get("date_from"):
        must.append({"range": {"interaction_date": {"gte": str(filters["date_from"])}}})
    if filters.get("date_to"):
        must.append({"range": {"interaction_date": {"lte": str(filters["date_to"])}}})
    if filters.get("topics"):
        topics = filters["topics"] if isinstance(filters["topics"], list) else [filters["topics"]]
        must.append({"terms": {"topics": topics}})
    return must


def keyword_search(query: str, filters: dict = None, page: int = 1, page_size: int = 20) -> dict:
    filters = filters or {}
    es = get_es_client()
    body = {
        "query": {
            "bool": {
                "must": [{
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "ai_summary^3",
                            "customer_requirements^2",
                            "pain_points^2",
                            "next_steps^2",
                            "raw_text",
                            "customer_name",
                        ],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                }],
                "filter": _build_es_filters(filters),
            }
        },
        "highlight": {
            "fields": {
                "ai_summary": {"fragment_size": 200, "number_of_fragments": 1},
                "raw_text": {"fragment_size": 200, "number_of_fragments": 1},
            }
        },
        "from": (page - 1) * page_size,
        "size": page_size,
    }
    return es.search(index=CONVERSATIONS_INDEX, body=body)


def semantic_search(query: str, filters: dict = None, page: int = 1, page_size: int = 20):
    from .embedding_service import generate_embedding
    from apps.conversations.models import Conversation
    from pgvector.django import CosineDistance

    filters = filters or {}
    query_embedding = generate_embedding(query)
    if query_embedding is None:
        return Conversation.objects.none()

    qs = Conversation.objects.filter(
        is_deleted=False, embedding__isnull=False
    ).annotate(
        similarity=CosineDistance("embedding", query_embedding)
    )

    if filters.get("customer"):
        qs = qs.filter(customer_id=filters["customer"])
    if filters.get("sentiment"):
        sentiments = filters["sentiment"] if isinstance(filters["sentiment"], list) else [filters["sentiment"]]
        qs = qs.filter(sentiment__in=sentiments)
    if filters.get("date_from"):
        qs = qs.filter(interaction_date__date__gte=filters["date_from"])
    if filters.get("date_to"):
        qs = qs.filter(interaction_date__date__lte=filters["date_to"])

    offset = (page - 1) * page_size
    return qs.order_by("similarity")[offset: offset + page_size]


def hybrid_search(query: str, filters: dict = None, page: int = 1, page_size: int = 20):
    filters = filters or {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        kw_future = executor.submit(keyword_search, query, filters, 1, 100)
        sem_future = executor.submit(semantic_search, query, filters, 1, 100)
        kw_results = kw_future.result()
        sem_results = list(sem_future.result())

    # Reciprocal Rank Fusion (k=60)
    scores = {}
    kw_hits = kw_results.get("hits", {}).get("hits", [])
    for rank, hit in enumerate(kw_hits, 1):
        cid = hit["_source"]["conversation_id"]
        scores[cid] = scores.get(cid, {"score": 0, "highlight": None})
        scores[cid]["score"] += 1 / (60 + rank)
        scores[cid]["highlight"] = hit.get("highlight")

    for rank, conv in enumerate(sem_results, 1):
        cid = str(conv.id)
        if cid not in scores:
            scores[cid] = {"score": 0, "highlight": None}
        scores[cid]["score"] += 1 / (60 + rank)

    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid]["score"], reverse=True)
    page_ids = sorted_ids[((page - 1) * page_size): (page * page_size)]

    from apps.conversations.models import Conversation
    conversations = {
        str(c.id): c
        for c in Conversation.objects.filter(id__in=page_ids).select_related("customer", "created_by")
    }
    ordered = [conversations[cid] for cid in page_ids if cid in conversations]

    return ordered, scores
