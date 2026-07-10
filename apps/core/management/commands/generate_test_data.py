import datetime
import random
from decimal import Decimal
from django.utils import timezone
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User, UserRole
from apps.inventory.models import ParkingSpot, LotOccupancy, SpotSizeType, SpotStatus, VehicleType
from apps.payments.models import PricingRule, Payment, PaymentMethod, PaymentStatus
from apps.gates.models import Ticket, TicketStatus

class Command(BaseCommand):
    help = 'Populates the database with initial test data for Parking Lot Management System'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to generate test data...")

        # 1. Create Users
        self.stdout.write("Creating users...")
        admin, _ = User.objects.get_or_create(username="admin", defaults={
            "email": "admin@example.com", "role": UserRole.ADMIN
        })
        if not admin.check_password("admin123"):
            admin.set_password("admin123")
            admin.save()
        
        attendant, _ = User.objects.get_or_create(username="attendant1", defaults={
            "email": "attendant1@example.com", "role": UserRole.ATTENDANT
        })
        if not attendant.check_password("attendant123"):
            attendant.set_password("attendant123")
            attendant.save()
        self.stdout.write(self.style.SUCCESS("Verified admin and attendant users"))

        # Clear existing dynamic data (Tickets, Payments)
        Payment.objects.all().delete()
        Ticket.objects.all().delete()
        ParkingSpot.objects.all().delete()
        LotOccupancy.objects.all().delete()

        # 2. Create Parking Spots
        self.stdout.write("Creating parking spots...")
        spots_to_create = []
        
        config = {
            SpotSizeType.COMPACT: 50,
            SpotSizeType.REGULAR: 100,
            SpotSizeType.OVERSIZED: 30,
        }

        spot_id_counter = 1
        for size, count in config.items():
            for i in range(count):
                prefix = size[0].upper() # C, R, O
                spots_to_create.append(
                    ParkingSpot(
                        spot_number=f"{prefix}-{spot_id_counter:04d}",
                        size_type=size,
                        status=SpotStatus.ACTIVE
                    )
                )
                spot_id_counter += 1
                
        ParkingSpot.objects.bulk_create(spots_to_create)
        self.stdout.write(self.style.SUCCESS(f"Created {len(spots_to_create)} parking spots"))

        # 3. Create Lot Occupancy Sentinel Rows
        self.stdout.write("Initializing Lot Occupancy...")
        occupancy_map = {}
        for size, count in config.items():
            occ = LotOccupancy.objects.create(
                spot_size=size, total_capacity=count, current_count=0, version=0
            )
            occupancy_map[size] = occ
        self.stdout.write(self.style.SUCCESS("Initialized Lot Occupancy counts"))

        # 4. Create Pricing Rules
        self.stdout.write("Creating Pricing Rules...")
        PricingRule.objects.all().delete()
        
        rules = [
            (VehicleType.MOTORCYCLE, SpotSizeType.COMPACT, '5.00', '25.00'),
            (VehicleType.MOTORCYCLE, SpotSizeType.REGULAR, '5.00', '25.00'),
            (VehicleType.MOTORCYCLE, SpotSizeType.OVERSIZED, '5.00', '25.00'),
            (VehicleType.CAR, SpotSizeType.REGULAR, '10.00', '50.00'),
            (VehicleType.CAR, SpotSizeType.OVERSIZED, '12.00', '60.00'),
            (VehicleType.TRUCK, SpotSizeType.OVERSIZED, '20.00', '100.00'),
        ]
        start_time, end_time = datetime.time(0, 0), datetime.time(23, 59, 59)
        for v_type, s_size, h_rate, d_rate in rules:
            PricingRule.objects.create(
                vehicle_type=v_type, spot_size=s_size, time_start=start_time,
                time_end=end_time, hourly_rate=Decimal(h_rate), max_daily_rate=Decimal(d_rate), is_active=True
            )

        # 5. Generate Active Tickets (Currently parked vehicles)
        self.stdout.write("Generating active tickets (parked vehicles)...")
        now = timezone.now()
        active_tickets_to_create = []
        # Let's fill 15 compact (Motorcycles), 40 regular (Cars), 10 oversized (Trucks)
        active_counts = {
            VehicleType.MOTORCYCLE: (15, SpotSizeType.COMPACT),
            VehicleType.CAR: (40, SpotSizeType.REGULAR),
            VehicleType.TRUCK: (10, SpotSizeType.OVERSIZED),
        }

        for v_type, (count, s_size) in active_counts.items():
            for i in range(count):
                entry = now - datetime.timedelta(hours=random.uniform(0.5, 5.0))
                ticket = Ticket(
                    vehicle_type=v_type, assigned_size=s_size, status=TicketStatus.OPEN, issued_by=attendant
                )
                active_tickets_to_create.append((ticket, entry))
            
            # Update OCC sentinel for this active batch
            occ = occupancy_map[s_size]
            occ.current_count += count
            occ.version += 1
            occ.save()

        # Save and override entry_time for accurate history
        for ticket, entry in active_tickets_to_create:
            ticket.save()
            Ticket.objects.filter(id=ticket.id).update(entry_time=entry)

        # 6. Generate Past Transactions (Historical data for revenue reports)
        self.stdout.write("Generating past tickets and payments...")
        past_dates = [now - datetime.timedelta(days=i) for i in range(1, 8)]
        
        for p_date in past_dates:
            # Create 10 historical payments per day
            for _ in range(10):
                v_type = random.choice([VehicleType.MOTORCYCLE, VehicleType.CAR, VehicleType.TRUCK])
                s_size = SpotSizeType.COMPACT if v_type == VehicleType.MOTORCYCLE else (SpotSizeType.REGULAR if v_type == VehicleType.CAR else SpotSizeType.OVERSIZED)
                entry = p_date - datetime.timedelta(hours=random.uniform(1.0, 8.0))
                
                # Create the ticket
                ticket = Ticket.objects.create(
                    vehicle_type=v_type, assigned_size=s_size, status=TicketStatus.PAID,
                    issued_by=attendant, exit_time=p_date
                )
                Ticket.objects.filter(id=ticket.id).update(entry_time=entry)

                # Create the payment
                amount = Decimal(random.randint(10, 50))
                pmt = Payment.objects.create(
                    ticket=ticket, processed_by=attendant, amount=amount,
                    payment_method=random.choice(PaymentMethod.choices)[0],
                    status=PaymentStatus.SUCCESS
                )
                Payment.objects.filter(id=pmt.id).update(payment_time=p_date)

        self.stdout.write(self.style.SUCCESS("Test data generation complete with tickets and payments!"))
