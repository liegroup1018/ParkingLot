"""
Initial migration — Track 1: Foundation & Identity.

Creates:
  - accounts_users        (Custom User model)
  - accounts_audit_logs   (AuditLog model)

All indexes defined in the models' Meta.indexes are applied here.
"""
import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        # ------------------------------------------------------------------
        # accounts_users
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("username", models.CharField(
                    error_messages={"unique": "A user with that username already exists."},
                    help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                    max_length=150,
                    unique=True,
                    validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                    verbose_name="username",
                )),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="email address")),
                ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
                ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active.", verbose_name="active")),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
                # Parking-lot specific fields
                ("role", models.CharField(
                    choices=[("ADMIN", "Management Admin"), ("ATTENDANT", "Parking Attendant")],
                    db_index=True,
                    default="ATTENDANT",
                    help_text="The RBAC role that controls which endpoints this user may access.",
                    max_length=20,
                )),
                ("two_factor_secret", models.CharField(
                    blank=True,
                    default="",
                    help_text="TOTP base32 secret (pyotp). Empty string means 2FA is not yet configured.",
                    max_length=64,
                )),
                # Relations
                ("groups", models.ManyToManyField(
                    blank=True,
                    help_text="The groups this user belongs to.",
                    related_name="user_set",
                    related_query_name="user",
                    to="auth.group",
                    verbose_name="groups",
                )),
                ("user_permissions", models.ManyToManyField(
                    blank=True,
                    help_text="Specific permissions for this user.",
                    related_name="user_set",
                    related_query_name="user",
                    to="auth.permission",
                    verbose_name="user permissions",
                )),
            ],
            options={
                "verbose_name": "User",
                "verbose_name_plural": "Users",
                "db_table": "accounts_users",
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        # Composite index: role + is_active
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["role", "is_active"], name="idx_users_role_active"),
        ),

        # ------------------------------------------------------------------
        # accounts_audit_logs
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="audit_logs",
                    to=settings.AUTH_USER_MODEL,
                    help_text="The user who initiated the action. NULL = system-generated.",
                )),
                ("action_type", models.CharField(
                    choices=[
                        ("MANUAL_GATE_OPEN", "Manual Gate Open"),
                        ("PRICE_CHANGE", "Price Rule Changed"),
                        ("SPOT_CREATED", "Parking Spot Created"),
                        ("SPOT_UPDATED", "Parking Spot Updated"),
                        ("SPOT_DELETED", "Parking Spot Deleted"),
                        ("USER_CREATED", "User Account Created"),
                        ("USER_DEACTIVATED", "User Account Deactivated"),
                        ("LOGIN_SUCCESS", "Successful Login"),
                        ("LOGIN_FAILED", "Failed Login Attempt"),
                        ("PASSWORD_CHANGED", "Password Changed"),
                        ("TICKET_VOIDED", "Ticket Voided"),
                        ("OCCUPANCY_RESET", "Lot Occupancy Reset"),
                    ],
                    db_index=True,
                    max_length=50,
                    help_text="Semantic code for the action that took place.",
                )),
                ("details", models.JSONField(
                    default=dict,
                    help_text="Arbitrary JSON payload describing the change.",
                )),
                ("ip_address", models.GenericIPAddressField(
                    blank=True,
                    null=True,
                    help_text="Source IP address of the HTTP request, if available.",
                )),
                ("timestamp", models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    help_text="UTC timestamp when the action occurred. Set automatically.",
                )),
            ],
            options={
                "verbose_name": "Audit Log",
                "verbose_name_plural": "Audit Logs",
                "db_table": "accounts_audit_logs",
                "ordering": ["-timestamp"],
            },
        ),
        # Composite indexes on AuditLog
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["user", "-timestamp"], name="idx_audit_user_timestamp"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["action_type", "-timestamp"], name="idx_audit_type_timestamp"),
        ),
    ]
