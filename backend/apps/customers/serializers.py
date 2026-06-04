from rest_framework import serializers
from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    conversation_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id", "name", "email", "phone", "company", "type",
            "notes", "zoho_record_id", "conversation_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "zoho_record_id", "created_at", "updated_at"]


class CustomerMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "email", "company", "type"]


class CustomerAutocompleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "email", "company", "type"]
