from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_assign_local_photo_images"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("cod", "Cash on Delivery"), ("razorpay", "Razorpay"), ("stripe", "Stripe")], max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("status", models.CharField(choices=[("initiated", "Initiated"), ("success", "Success"), ("failed", "Failed")], default="initiated", max_length=20)),
                ("reference", models.CharField(max_length=64, unique=True)),
                ("provider_payment_id", models.CharField(blank=True, max_length=120)),
                ("failure_reason", models.CharField(blank=True, max_length=255)),
                ("gateway_response", models.JSONField(blank=True, default=dict)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="core.order")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
