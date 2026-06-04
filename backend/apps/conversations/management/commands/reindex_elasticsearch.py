from django.core.management.base import BaseCommand

from apps.conversations.models import Conversation
from apps.conversations.services.search_service import ensure_index_exists, index_conversation


class Command(BaseCommand):
    help = "Re-index all completed conversations in Elasticsearch"

    def handle(self, *args, **options):
        ensure_index_exists()

        conversations = Conversation.objects.filter(
            is_deleted=False, ai_status="completed"
        ).select_related("customer", "created_by")

        total = conversations.count()
        self.stdout.write(f"Indexing {total} conversations...")

        success = 0
        failed = 0
        for i, conversation in enumerate(conversations, 1):
            if index_conversation(conversation):
                success += 1
            else:
                failed += 1
            if i % 50 == 0:
                self.stdout.write(f"  Progress: {i}/{total}")

        self.stdout.write(self.style.SUCCESS(f"Done. Success: {success}, Failed: {failed}"))
