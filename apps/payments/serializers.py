from rest_framework import serializers

from apps.gates.models import Ticket
from apps.payments.models import Payment, PaymentMethod

class TicketScanSerializer(serializers.Serializer):
    ticket_code = serializers.CharField(max_length=50)

class PaymentCreateSerializer(serializers.ModelSerializer):
    ticket_id = serializers.CharField(max_length=50, write_only=True)
    amount_paid = serializers.DecimalField(max_digits=8, decimal_places=2, write_only=True)
    method = serializers.ChoiceField(choices=PaymentMethod.choices, write_only=True)
    processed_by = serializers.CharField(max_length=50, write_only=True, required=False)

    class Meta:
        model = Payment
        fields = ['ticket_id', 'amount_paid', 'method', 'processed_by', 'id', 'amount', 'payment_time', 'status']
        read_only_fields = ['id', 'amount', 'payment_time', 'status']

