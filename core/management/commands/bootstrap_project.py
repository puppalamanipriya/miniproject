from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Category, Coupon, Product, UserProfile


class Command(BaseCommand):
    help = "Create admin access, demo user, and starter catalog data."

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default="admin")
        parser.add_argument("--admin-email", default="admin@example.com")
        parser.add_argument("--admin-password", default="Admin@12345")
        parser.add_argument("--demo-username", default="demo")
        parser.add_argument("--demo-email", default="demo@example.com")
        parser.add_argument("--demo-password", default="Demo@12345")

    def handle(self, *args, **options):
        user_model = get_user_model()

        admin_username = options["admin_username"]
        admin_email = options["admin_email"]
        admin_password = options["admin_password"]
        demo_username = options["demo_username"]
        demo_email = options["demo_email"]
        demo_password = options["demo_password"]

        admin_user, admin_created = user_model.objects.get_or_create(
            username=admin_username,
            defaults={"email": admin_email, "is_staff": True, "is_superuser": True},
        )
        admin_user.email = admin_email
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        admin_user.set_password(admin_password)
        admin_user.save()
        admin_profile, _ = UserProfile.objects.get_or_create(user=admin_user)
        if not admin_profile.email_verified:
            admin_profile.email_verified = True
            admin_profile.save(update_fields=["email_verified"])

        demo_user, demo_created = user_model.objects.get_or_create(
            username=demo_username,
            defaults={"email": demo_email, "is_active": True},
        )
        demo_user.email = demo_email
        demo_user.is_active = True
        demo_user.set_password(demo_password)
        demo_user.save()
        demo_profile, _ = UserProfile.objects.get_or_create(user=demo_user)
        if not demo_profile.email_verified:
            demo_profile.email_verified = True
            demo_profile.save(update_fields=["email_verified"])

        categories = [
            ("Bottles", "bottles"),
            ("Cans", "cans"),
            ("Jars", "jars"),
        ]
        for name, slug in categories:
            Category.objects.get_or_create(slug=slug, defaults={"name": name})

        starter_products = [
            {
                "name": "Original Daily",
                "slug": "bottles",
                "volume_label": "1L",
                "price": Decimal("25.00"),
                "description": "Daily hydration bottle.",
                "stock_quantity": 120,
                "is_featured": True,
                "image_url": "/static/core/products/photos/bottle-medium-photo.png",
            },
            {
                "name": "Original Family",
                "slug": "bottles",
                "volume_label": "2L",
                "price": Decimal("45.00"),
                "description": "Family-size bottle pack.",
                "stock_quantity": 90,
                "is_featured": True,
                "image_url": "/static/core/products/photos/bottle-large-photo.png",
            },
            {
                "name": "Can 5L",
                "slug": "cans",
                "volume_label": "5L",
                "price": Decimal("110.00"),
                "description": "Mid-size can for regular use.",
                "stock_quantity": 60,
                "is_featured": False,
                "image_url": "/static/core/products/photos/can-photo.png",
            },
            {
                "name": "Jar 20L",
                "slug": "jars",
                "volume_label": "20L",
                "price": Decimal("160.00"),
                "description": "Large jar for home and office.",
                "stock_quantity": 40,
                "is_featured": True,
                "image_url": "/static/core/products/photos/jar-photo.png",
            },
        ]

        for product_data in starter_products:
            category = Category.objects.get(slug=product_data.pop("slug"))
            Product.objects.get_or_create(
                name=product_data["name"],
                volume_label=product_data["volume_label"],
                defaults={**product_data, "category": category},
            )

        now = timezone.now()
        coupon, coupon_created = Coupon.objects.get_or_create(
            code="WELCOME10",
            defaults={
                "discount_percent": 10,
                "is_active": True,
                "valid_from": now - timedelta(days=1),
                "valid_to": now + timedelta(days=365),
                "minimum_order_amount": Decimal("100.00"),
            },
        )
        if not coupon_created:
            coupon.is_active = True
            coupon.valid_from = now - timedelta(days=1)
            coupon.valid_to = now + timedelta(days=365)
            coupon.discount_percent = 10
            coupon.minimum_order_amount = Decimal("100.00")
            coupon.save(
                update_fields=[
                    "is_active",
                    "valid_from",
                    "valid_to",
                    "discount_percent",
                    "minimum_order_amount",
                ]
            )

        self.stdout.write(self.style.SUCCESS("Bootstrap completed successfully."))
        self.stdout.write(
            f"Admin: username={admin_username} password={admin_password} "
            f"({'created' if admin_created else 'updated'})"
        )
        self.stdout.write(
            f"Demo: username={demo_username} password={demo_password} "
            f"({'created' if demo_created else 'updated'})"
        )
        self.stdout.write("Coupon: WELCOME10 (10% off above 100.00)")
