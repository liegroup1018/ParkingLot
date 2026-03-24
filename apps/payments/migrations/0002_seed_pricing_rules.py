from django.db import migrations

def seed_pricing_rules(apps, schema_editor):
    PricingRule = apps.get_model('payments', 'PricingRule')
    
    rules = [
        # Motorcycle Pricing
        {"vehicle_type": "MOTORCYCLE", "spot_size": "COMPACT", "time_start": "00:00:00", "time_end": "23:59:59", "hourly_rate": 2.00, "max_daily_rate": 20.00},
        {"vehicle_type": "MOTORCYCLE", "spot_size": "REGULAR", "time_start": "00:00:00", "time_end": "23:59:59", "hourly_rate": 3.00, "max_daily_rate": 30.00},
        {"vehicle_type": "MOTORCYCLE", "spot_size": "OVERSIZED", "time_start": "00:00:00", "time_end": "23:59:59", "hourly_rate": 4.00, "max_daily_rate": 40.00},
        
        # Car Pricing
        {"vehicle_type": "CAR", "spot_size": "REGULAR", "time_start": "00:00:00", "time_end": "23:59:59", "hourly_rate": 5.00, "max_daily_rate": 40.00},
        {"vehicle_type": "CAR", "spot_size": "OVERSIZED", "time_start": "00:00:00", "time_end": "23:59:59", "hourly_rate": 6.00, "max_daily_rate": 50.00},
        
        # Truck Pricing
        {"vehicle_type": "TRUCK", "spot_size": "OVERSIZED", "time_start": "00:00:00", "time_end": "23:59:59", "hourly_rate": 10.00, "max_daily_rate": 80.00},
    ]

    for rule_data in rules:
        PricingRule.objects.create(**rule_data)

def reverse_seed_pricing_rules(apps, schema_editor):
    PricingRule = apps.get_model('payments', 'PricingRule')
    PricingRule.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_pricing_rules, reverse_seed_pricing_rules),
    ]
