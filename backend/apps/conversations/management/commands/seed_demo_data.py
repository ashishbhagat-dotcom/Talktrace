import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.conversations.models import ActionItem, Conversation
from apps.customers.models import Customer

User = get_user_model()

CUSTOMERS = [
    {"name": "Priya Sharma", "company": "TechNova Solutions", "email": "priya@technova.io", "phone": "+91 98765 43210", "type": "contact"},
    {"name": "Rohan Mehta", "company": "CloudEdge Systems", "email": "rohan@cloudedge.com", "phone": "+91 87654 32109", "type": "lead"},
    {"name": "Ananya Singh", "company": "DataBridge Analytics", "email": "ananya@databridge.in", "phone": "+91 76543 21098", "type": "account"},
    {"name": "Vikram Nair", "company": "FinAxis Consulting", "email": "vikram@finaxis.com", "phone": "+91 65432 10987", "type": "lead"},
    {"name": "Meera Patel", "company": "GreenLeaf Retail", "email": "meera@greenleaf.in", "phone": "+91 54321 09876", "type": "contact"},
]

CONVERSATIONS_DATA = [
    {
        "type": "phone_call",
        "raw_text": "Had a 30-minute call with Priya from TechNova. They're looking to replace their current CRM system which is Salesforce. Main pain point is the cost — they're paying $4,000/month and finding it too expensive for their 15-member sales team. They need better integration with their existing tools like Slack and Jira. Priya mentioned their contract with Salesforce ends in 3 months so timing is perfect. She wants a demo next week with their team lead Arun. Budget is around $1,500/month.",
        "sentiment": "positive",
        "sentiment_score": 0.7,
        "ai_summary": "TechNova is actively evaluating CRM alternatives due to high Salesforce costs. Strong buying intent with contract ending in 3 months. Demo requested with decision-maker.",
        "topics": ["CRM migration", "pricing", "Salesforce competitor", "demo request"],
        "competitor_mentions": ["Salesforce"],
        "days_ago": 2,
    },
    {
        "type": "video_call",
        "raw_text": "Video demo with Rohan from CloudEdge. They're a fast-growing startup (Series A, 45 employees) looking for a conversation intelligence tool for their sales team. Their current process is manual — reps take notes in Notion after calls. They love the idea of auto-transcription and AI summaries. Main concern was data privacy — where is the data stored? They want everything on-premise or in Indian data centers. Also asked about GDPR compliance. Their sales cycle is 6-8 weeks. Asked for pricing for 20 seats.",
        "sentiment": "neutral",
        "sentiment_score": 0.2,
        "ai_summary": "CloudEdge is interested but has strong data residency requirements. On-premise or Indian DC hosting is a blocker. Need to clarify compliance posture before moving forward.",
        "topics": ["data privacy", "on-premise", "GDPR", "pricing", "startup"],
        "competitor_mentions": [],
        "days_ago": 5,
    },
    {
        "type": "in_person",
        "raw_text": "In-person meeting at DataBridge office in Bangalore. Met with Ananya (VP Sales) and her team of 3 sales managers. They have been a customer for 6 months and want to upgrade their plan. Current plan is Basic (5 users) and they want to add 10 more users. They're very happy with the AI summarization feature — saving 2 hours/day per rep. Main ask is a team analytics dashboard to track rep performance. Also requested Zoho CRM integration since they use Zoho. Willing to sign a 12-month contract if we can offer 15% discount.",
        "sentiment": "very_positive",
        "sentiment_score": 0.9,
        "ai_summary": "Existing customer expansion opportunity. 10-seat upsell with annual contract possible at 15% discount. Feature requests: team analytics dashboard and Zoho CRM integration.",
        "topics": ["upsell", "annual contract", "Zoho integration", "team analytics", "expansion"],
        "competitor_mentions": ["Zoho"],
        "days_ago": 7,
    },
    {
        "type": "phone_call",
        "raw_text": "Follow-up call with Vikram from FinAxis. He was not happy — their implementation has been delayed by 2 weeks and their team is frustrated. The main issue is that the audio transcription quality for Hindi-English mixed conversations (Hinglish) is poor. About 40% of their calls are in Hinglish and the accuracy is only around 60%. He's considering moving to a competitor. I escalated to the product team. Need to provide a resolution within 48 hours or we risk losing this account.",
        "sentiment": "very_negative",
        "sentiment_score": -0.85,
        "ai_summary": "At-risk account. Implementation delays and poor Hinglish transcription accuracy causing frustration. Immediate escalation needed — 48-hour resolution window before potential churn.",
        "topics": ["churn risk", "transcription quality", "Hinglish", "implementation delay", "escalation"],
        "competitor_mentions": [],
        "days_ago": 1,
    },
    {
        "type": "whatsapp",
        "raw_text": "WhatsApp conversation with Meera from GreenLeaf Retail. She's a new lead referred by DataBridge. GreenLeaf has 8 field sales reps who visit stores across Mumbai and need to log conversations on mobile. Key requirement: offline-first mobile app — their reps often have poor connectivity in stores. Also need voice memo support in Hindi. Budget is limited — looking for something under $500/month. They want to pilot with 3 users first before full rollout.",
        "sentiment": "neutral",
        "sentiment_score": 0.1,
        "ai_summary": "Referral lead from existing customer. Mobile-first with offline support is hard requirement. Hindi voice support needed. Small initial budget but potential for full rollout.",
        "topics": ["mobile app", "offline support", "field sales", "Hindi", "pilot"],
        "competitor_mentions": [],
        "days_ago": 3,
    },
    {
        "type": "video_call",
        "raw_text": "Second demo with TechNova — this time Priya brought Arun (Head of Sales) and Kiran (IT Manager). Arun loved the search feature — found it much better than Salesforce's. Kiran asked about SSO/SAML integration and API access. We confirmed both are available on the Enterprise plan. Arun is pushing to sign before month-end for budget reasons. Main remaining concern is migration of 3 years of Salesforce data. I committed to a free data migration service as part of the deal.",
        "sentiment": "very_positive",
        "sentiment_score": 0.88,
        "ai_summary": "Deal is close to closing. Decision-makers engaged. SSO/SAML confirmed. Free data migration offered as incentive. Strong urgency from budget cycle — push for month-end close.",
        "topics": ["demo", "enterprise", "SSO", "data migration", "closing"],
        "competitor_mentions": ["Salesforce"],
        "days_ago": 0,
    },
    {
        "type": "email",
        "raw_text": "Email thread with Rohan (CloudEdge) after initial demo. He came back with specific questions: 1) Can we sign a data processing agreement (DPA)? 2) Is the data encrypted at rest and in transit? 3) Do we have SOC 2 Type II certification? 4) Can they do a security audit before signing? I replied confirming DPA availability, AES-256 encryption, and that SOC 2 Type II is in progress (expected Q3). Offered a security questionnaire instead of audit. He seems satisfied with the answers. Moving to pricing discussion.",
        "sentiment": "positive",
        "sentiment_score": 0.5,
        "ai_summary": "Security compliance questions addressed. DPA available, encryption confirmed, SOC 2 in progress. CloudEdge moving to pricing stage despite initial compliance concerns.",
        "topics": ["security", "compliance", "DPA", "SOC 2", "encryption"],
        "competitor_mentions": [],
        "days_ago": 4,
    },
    {
        "type": "phone_call",
        "raw_text": "Urgent call with Vikram — following up on the Hinglish issue escalation. The product team deployed a fix using a bilingual Whisper model fine-tuned on Hinglish. Vikram tested it and accuracy improved from 60% to 85%. He's happy with the progress but wants it to reach 90%+ before full rollout. We agreed on a 2-week monitoring period. Offered 1 month free as goodwill gesture. He accepted and agreed to stay. Implementation back on track.",
        "sentiment": "positive",
        "sentiment_score": 0.6,
        "ai_summary": "Churn crisis resolved. Hinglish accuracy improved to 85% with new model. 2-week monitoring period agreed. 1 month free offered as goodwill — customer retained.",
        "topics": ["customer retention", "Hinglish fix", "product improvement", "goodwill"],
        "competitor_mentions": [],
        "days_ago": 0,
    },
]

ACTION_ITEMS_DATA = [
    "Send demo recording to Priya at TechNova",
    "Prepare 12-month pricing proposal for DataBridge with 15% discount",
    "Escalate Hinglish transcription issue to product team",
    "Schedule follow-up demo for CloudEdge with security team",
    "Send data migration guide to TechNova IT team",
    "Create pilot proposal (3 users, 30 days) for GreenLeaf",
    "Follow up with Rohan on SOC 2 timeline",
    "Prepare Zoho integration roadmap for DataBridge",
    "Send Vikram goodwill email + 1 month free coupon",
    "Research offline mobile app feasibility for GreenLeaf",
]


class Command(BaseCommand):
    help = "Seed demo data: 5 customers, 8 conversations, 10 action items"

    def handle(self, *args, **options):
        self.stdout.write("Seeding demo data...")

        # Create demo users
        admin_user, _ = User.objects.get_or_create(
            email="admin@talktrace.io",
            defaults={"name": "Admin User", "role": "admin", "is_staff": True, "is_superuser": True},
        )
        admin_user.set_password("admin123")
        admin_user.save()

        sales_user, _ = User.objects.get_or_create(
            email="sales@talktrace.io",
            defaults={"name": "Sales Rep", "role": "member"},
        )
        sales_user.set_password("sales123")
        sales_user.save()

        users = [admin_user, sales_user]
        self.stdout.write(f"  ✓ Users: admin@talktrace.io / sales@talktrace.io (password: admin123 / sales123)")

        # Create customers
        customers = []
        for data in CUSTOMERS:
            customer, created = Customer.objects.get_or_create(
                email=data["email"], defaults=data
            )
            customers.append(customer)
        self.stdout.write(f"  ✓ {len(customers)} customers created")

        # Create conversations
        conversations = []
        for i, data in enumerate(CONVERSATIONS_DATA):
            customer = customers[i % len(customers)]
            interaction_date = timezone.now() - timedelta(days=data["days_ago"])
            conversation, created = Conversation.objects.get_or_create(
                customer=customer,
                interaction_date__date=interaction_date.date(),
                conversation_type=data["type"],
                defaults={
                    "raw_text": data["raw_text"],
                    "ai_summary": data["ai_summary"],
                    "sentiment": data["sentiment"],
                    "sentiment_score": data["sentiment_score"],
                    "topics": data["topics"],
                    "competitor_mentions": data["competitor_mentions"],
                    "ai_status": "completed",
                    "created_by": random.choice(users),
                    "interaction_date": interaction_date,
                    "customer_requirements": f"Requirements extracted from: {data['raw_text'][:100]}...",
                    "next_steps": "Follow up as discussed.",
                },
            )
            conversations.append(conversation)
        self.stdout.write(f"  ✓ {len(conversations)} conversations created")

        # Create action items
        for i, desc in enumerate(ACTION_ITEMS_DATA):
            conversation = conversations[i % len(conversations)]
            ActionItem.objects.get_or_create(
                conversation=conversation,
                description=desc,
                defaults={
                    "assigned_to": random.choice(users),
                    "status": random.choice(["pending", "pending", "in_progress", "completed"]),
                    "priority": random.choice(["low", "medium", "high"]),
                    "due_date": (timezone.now() + timedelta(days=random.randint(-2, 14))).date(),
                },
            )
        self.stdout.write(f"  ✓ {len(ACTION_ITEMS_DATA)} action items created")

        # Generate embeddings and index in Elasticsearch
        self.stdout.write("Generating embeddings and indexing...")
        try:
            from apps.conversations.services.embedding_service import generate_embedding
            from apps.conversations.services.search_service import ensure_index_exists, index_conversation

            ensure_index_exists()
            indexed = 0
            for conv in conversations:
                text = " ".join(filter(None, [conv.ai_summary, conv.raw_text[:500]]))
                emb = generate_embedding(text)
                if emb:
                    conv.embedding = emb
                    conv.save(update_fields=["embedding"])
                index_conversation(conv)
                indexed += 1
            self.stdout.write(f"  ✓ {indexed} conversations embedded and indexed")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  ⚠ Embedding/indexing skipped: {e}"))

        self.stdout.write(self.style.SUCCESS("\nDemo data seeded successfully!"))
        self.stdout.write("  Login: admin@talktrace.io / admin123")
        self.stdout.write("  Login: sales@talktrace.io / sales123")
