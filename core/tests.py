from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Cart, CartItem, Coupon, Order, Product, Subscription, UserProfile


class AuthFlowTests(TestCase):
    def test_signup_creates_user_and_profile(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "alice",
                "email": "alice@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="alice")
        self.assertEqual(user.email, "alice@example.com")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_home_requires_login(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_login_and_logout_flow(self):
        user = User.objects.create_user(
            username="charlie",
            email="charlie@example.com",
            password="StrongPass123!",
        )
        response = self.client.post(
            reverse("login"),
            {"username": "charlie", "password": "StrongPass123!", "next": reverse("shop")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("shop"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)

        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_blocks_external_next_redirect(self):
        User.objects.create_user(
            username="delta",
            email="delta@example.com",
            password="StrongPass123!",
        )
        response = self.client.post(
            reverse("login"),
            {
                "username": "delta",
                "password": "StrongPass123!",
                "next": "https://malicious.example/phish",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))


class CartCheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bob", password="StrongPass123!", email="bob@test.com")
        self.product = Product.objects.create(
            name="Bottle", volume_label="1L", price="100.00", stock_quantity=20
        )

    def test_add_to_cart_creates_cart_item(self):
        self.client.login(username="bob", password="StrongPass123!")
        response = self.client.post(reverse("add_to_cart", args=[self.product.id]), {"quantity": 2})
        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(user=self.user)
        item = CartItem.objects.get(cart=cart, product=self.product)
        self.assertEqual(item.quantity, 2)

    def test_guest_add_to_cart_uses_session(self):
        response = self.client.post(reverse("add_to_cart", args=[self.product.id]), {"quantity": 2})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("cart_items"), {str(self.product.id): 2})

    def test_guest_cart_merges_on_login(self):
        self.client.post(reverse("add_to_cart", args=[self.product.id]), {"quantity": 3})
        response = self.client.post(
            reverse("login"),
            {"username": "bob", "password": "StrongPass123!", "next": reverse("shop")},
        )
        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(user=self.user)
        item = CartItem.objects.get(cart=cart, product=self.product)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(self.client.session.get("cart_items"), {})

    def test_checkout_creates_order_with_coupon_discount(self):
        self.client.login(username="bob", password="StrongPass123!")
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        Coupon.objects.create(
            code="SAVE10",
            discount_percent=10,
            is_active=True,
            valid_from=timezone.now() - timedelta(days=1),
            valid_to=timezone.now() + timedelta(days=1),
            minimum_order_amount="100.00",
        )
        response = self.client.post(
            reverse("checkout"),
            {
                "delivery_name": "Bob",
                "delivery_phone": "9999999999",
                "delivery_address": "Street 1",
                "delivery_city": "Bengaluru",
                "delivery_pincode": "560001",
                "coupon_code": "SAVE10",
                "payment_method": "cod",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.subtotal_amount, 200)
        self.assertEqual(order.discount_amount, 20)
        self.assertEqual(order.total_amount, 180)

    def test_checkout_creates_weekly_subscription(self):
        self.client.login(username="bob", password="StrongPass123!")
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)

        response = self.client.post(
            reverse("checkout"),
            {
                "delivery_name": "Bob",
                "delivery_phone": "9999999999",
                "delivery_address": "Street 1",
                "delivery_city": "Bengaluru",
                "delivery_pincode": "560001",
                "payment_method": "cod",
                "fulfillment_type": "weekly",
            },
        )
        self.assertEqual(response.status_code, 302)

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.fulfillment_type, Order.FULFILLMENT_WEEKLY)
        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.frequency, Subscription.FREQ_WEEKLY)
        self.assertEqual(subscription.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(subscription.last_order, order)
