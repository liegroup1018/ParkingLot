from rest_framework import serializers

from apps.gates.models import Ticket
from apps.payments.models import Payment, PaymentMethod, PricingRule

class TicketScanSerializer(serializers.Serializer):
    ticket_code = serializers.CharField(max_length=50)

class PaymentCreateSerializer(serializers.ModelSerializer):
    ticket_id = serializers.CharField(max_length=50, write_only=True)
    amount_paid = serializers.DecimalField(max_digits=8, decimal_places=2, write_only=True)
    method = serializers.ChoiceField(choices=PaymentMethod.choices, write_only=True)

    class Meta:
        model = Payment
        fields = ['ticket_id', 'amount_paid', 'method', 'id', 'amount', 'payment_time', 'status']
        read_only_fields = ['id', 'amount', 'payment_time', 'status']


class PricingRuleReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingRule
        fields = [
            'id', 'vehicle_type', 'spot_size', 'time_start', 'time_end',
            'hourly_rate', 'max_daily_rate', 'is_active'
        ]

class PricingRuleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingRule
        fields = ['hourly_rate', 'max_daily_rate', 'is_active']

