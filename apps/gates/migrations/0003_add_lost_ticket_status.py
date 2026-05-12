from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gates", "0002_alter_ticket_assigned_size_alter_ticket_entry_time"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="ticket",
            name="chk_ticket_status_valid",
        ),
        migrations.AlterField(
            model_name="ticket",
            name="status",
            field=models.CharField(
                choices=[
                    ("OPEN", "Open"),
                    ("PAID", "Paid"),
                    ("LOST", "Lost"),
                    ("VOIDED", "Voided"),
                ],
                db_index=True,
                default="OPEN",
                help_text="Lifecycle state of the parking session.",
                max_length=10,
            ),
        ),
        migrations.AddConstraint(
            model_name="ticket",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["OPEN", "PAID", "LOST", "VOIDED"]),
                name="chk_ticket_status_valid",
            ),
        ),
    ]
