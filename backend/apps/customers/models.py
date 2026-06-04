import uuid
from django.db import models


class Customer(models.Model):
    class Type(models.TextChoices):
        LEAD = "lead", "Lead"
        CONTACT = "contact", "Contact"
        ACCOUNT = "account", "Account"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    company = models.CharField(max_length=255, blank=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.LEAD)
    notes = models.TextField(blank=True)
    zoho_record_id = models.CharField(max_length=50, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers_customer"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["company"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        if self.company:
            return f"{self.name} ({self.company})"
        return self.name
