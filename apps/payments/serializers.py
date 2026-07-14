from decimal import Decimal

from rest_framework import serializers

from apps.gates.models import Ticket
from apps.payments.models import Payment, PaymentMethod, PricingRule
from apps.inventory.models import VehicleType

class TicketScanSerializer(serializers.Serializer):
    """
    Validates the ticket_code before processing a payment.
    """
    ticket_code = serializers.CharField(max_length=50)

class LostTicketCreateSerializer(serializers.Serializer):
    """
    Validates the vehicle type for creating a lost ticket substitute.
    """
    vehicle_type = serializers.ChoiceField(choices=VehicleType.choices)

class PaymentCreateSerializer(serializers.ModelSerializer):
    """
    Validates the incoming payment request and maps fields for internal processing.
    """
    ticket_id = serializers.CharField(max_length=50, write_only=True)
    amount_paid = serializers.DecimalField(max_digits=8, decimal_places=2, write_only=True)
    method = serializers.ChoiceField(choices=PaymentMethod.choices, write_only=True)

    class Meta:
        model = Payment
        fields = ['ticket_id', 'amount_paid', 'method', 'id', 'amount', 'payment_time', 'status']
        read_only_fields = ['id', 'amount', 'payment_time', 'status']


class PricingRuleReadSerializer(serializers.ModelSerializer):
    """
    Safe read-only representation of pricing rules.
    """
    class Meta:
        model = PricingRule
        fields = [
            'id', 'vehicle_type', 'spot_size', 'time_start', 'time_end',
            'hourly_rate', 'max_daily_rate', 'is_active'
        ]

class PricingRuleUpdateSerializer(serializers.ModelSerializer):
    """
    Validates updates to existing pricing rules. Only rates and active state can be changed.
    """
    class Meta:
        model = PricingRule
        fields = ['hourly_rate', 'max_daily_rate', 'is_active']

    def validate_hourly_rate(self, value):
        if value <= Decimal("0.00"):
            raise serializers.ValidationError("Hourly rate must be greater than zero.")
        return value

    def validate_max_daily_rate(self, value):
        if value <= Decimal("0.00"):
            raise serializers.ValidationError("Maximum daily rate must be greater than zero.")
        return value
