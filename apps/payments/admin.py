from django.contrib import admin

from .models import PricingRule, Payment


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = (
        "vehicle_type", "spot_size", "hourly_rate",
        "max_daily_rate", "time_start", "time_end", "is_active",
    )
    list_filter = ("vehicle_type", "spot_size", "is_active")
    list_editable = ("hourly_rate", "max_daily_rate", "is_active")
    ordering = ("vehicle_type", "spot_size")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "ticket", "amount", "payment_method",
        "status", "payment_time", "processed_by",
    )
    list_filter = ("payment_method", "status", "payment_time")
    search_fields = ("ticket__ticket_code",)
    readonly_fields = ("ticket", "amount", "payment_method", "payment_time", "status", "processed_by")
    date_hierarchy = "payment_time"
    ordering = ("-payment_time",)
