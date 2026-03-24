from django.db import models
from django.conf import settings

from apps.inventory.models import SpotSizeType, VehicleType

class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    CREDIT = "CREDIT", "Credit Card"
    MOBILE = "MOBILE", "Mobile App"

class PaymentStatus(models.TextChoices):
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"

class PricingRule(models.Model):
    vehicle_type = models.CharField(
        max_length=15,
        choices=VehicleType.choices,
        db_index=True,
    )
    spot_size = models.CharField(
        max_length=15,
        choices=SpotSizeType.choices,
        db_index=True,
    )
    time_start = models.TimeField(help_text="Start time of this rule")
    time_end = models.TimeField(help_text="End time of this rule (inclusive)")
    hourly_rate = models.DecimalField(max_digits=6, decimal_places=2)
    max_daily_rate = models.DecimalField(max_digits=6, decimal_places=2)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments_pricing_rules"
        ordering = ["vehicle_type", "spot_size", "time_start"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(vehicle_type__in=VehicleType.values),
                name="chk_pricing_vehicle_type_valid",
            ),
            models.CheckConstraint(
                check=models.Q(spot_size__in=SpotSizeType.values),
                name="chk_pricing_spot_size_valid",
            ),
        ]

    def __str__(self):
        return f"{self.vehicle_type} in {self.spot_size}: ${self.hourly_rate}/hr"

class Payment(models.Model):
    ticket = models.ForeignKey(
        "gates.Ticket",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_method = models.CharField(
        max_length=15,
        choices=PaymentMethod.choices,
    )
    payment_time = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.CharField(
        max_length=15,
        choices=PaymentStatus.choices,
        default=PaymentStatus.SUCCESS,
        db_index=True,
    )

    class Meta:
        db_table = "payments_transactions"
        ordering = ["-payment_time"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(payment_method__in=PaymentMethod.values),
                name="chk_payment_method_valid",
            ),
            models.CheckConstraint(
                check=models.Q(status__in=PaymentStatus.values),
                name="chk_payment_status_valid",
            ),
        ]

    def __str__(self):
        return f"Payment {self.id} for Ticket {self.ticket_id} - ${self.amount}"
