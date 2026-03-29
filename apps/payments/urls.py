from django.urls import path
from apps.payments.views import (
    TicketScanView, PaymentProcessView,
    PricingRuleUpdateView, RevenueReportView, PeakHoursReportView
)

urlpatterns = [
    path("tickets/scan", TicketScanView.as_view(), name="ticket-scan"),
    path("payments", PaymentProcessView.as_view(), name="process-payment"),
    path("pricing-rules/<int:pk>", PricingRuleUpdateView.as_view(), name="pricing-rule-detail"),
    path("reports/revenue", RevenueReportView.as_view(), name="reports-revenue"),
    path("reports/peak-hours", PeakHoursReportView.as_view(), name="reports-peak-hours"),
]
