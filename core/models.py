from django.conf import settings
from django.db import models
from django.templatetags.static import static
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category, related_name="products", on_delete=models.SET_NULL, null=True, blank=True
    )
    name = models.CharField(max_length=120)
    volume_label = models.CharField(max_length=50, default="1L")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.CharField(max_length=500, blank=True)
    description = models.CharField(max_length=255, blank=True)
    stock_quantity = models.PositiveIntegerField(default=50)
    low_stock_threshold = models.PositiveIntegerField(default=10)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def resolved_image_url(self):
        if not self.image_url:
            return static("core/products/original-default.svg")
        if self.image_url.startswith(("http://", "https://", "/")):
            return self.image_url
        return static(self.image_url.lstrip("/"))

    def __str__(self):
        return f"{self.name} ({self.volume_label})"


class Order(models.Model):
    STATUS_PLACED = "placed"
    STATUS_PACKED = "packed"
    STATUS_OUT_FOR_DELIVERY = "out_for_delivery"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_PLACED, "Placed"),
        (STATUS_PACKED, "Packed"),
        (STATUS_OUT_FOR_DELIVERY, "Out for Delivery"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    )
    PAYMENT_COD = "cod"
    PAYMENT_RAZORPAY = "razorpay"
    PAYMENT_STRIPE = "stripe"
    PAYMENT_CHOICES = (
        (PAYMENT_COD, "Cash on Delivery"),
        (PAYMENT_RAZORPAY, "Razorpay"),
        (PAYMENT_STRIPE, "Stripe"),
    )
    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_FAILED, "Failed"),
    )
    FULFILLMENT_ONE_TIME = "one_time"
    FULFILLMENT_WEEKLY = "weekly"
    FULFILLMENT_MONTHLY = "monthly"
    FULFILLMENT_CHOICES = (
        (FULFILLMENT_ONE_TIME, "One-time"),
        (FULFILLMENT_WEEKLY, "Weekly Subscription"),
        (FULFILLMENT_MONTHLY, "Monthly Subscription"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="orders", on_delete=models.CASCADE, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_name = models.CharField(max_length=120, blank=True)
    delivery_phone = models.CharField(max_length=20, blank=True)
    delivery_address = models.CharField(max_length=255, blank=True)
    delivery_city = models.CharField(max_length=100, blank=True)
    delivery_pincode = models.CharField(max_length=12, blank=True)
    tracking_status = models.CharField(max_length=40, choices=STATUS_CHOICES, default=STATUS_PLACED)
    current_location = models.CharField(max_length=120, default="WaterSupply Warehouse")
    tracking_latitude = models.DecimalField(max_digits=9, decimal_places=6, default=12.971600)
    tracking_longitude = models.DecimalField(max_digits=9, decimal_places=6, default=77.594600)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_COD)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING
    )
    fulfillment_type = models.CharField(
        max_length=20, choices=FULFILLMENT_CHOICES, default=FULFILLMENT_ONE_TIME
    )
    coupon_code = models.CharField(max_length=40, blank=True)
    invoice_number = models.CharField(max_length=40, blank=True)
    is_return_requested = models.BooleanField(default=False)
    return_reason = models.CharField(max_length=255, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Subscription(models.Model):
    FREQ_WEEKLY = "weekly"
    FREQ_MONTHLY = "monthly"
    FREQUENCY_CHOICES = (
        (FREQ_WEEKLY, "Weekly"),
        (FREQ_MONTHLY, "Monthly"),
    )
    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_PAUSED, "Paused"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="subscriptions", on_delete=models.CASCADE)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField()
    next_delivery_date = models.DateField()
    delivery_name = models.CharField(max_length=120)
    delivery_phone = models.CharField(max_length=20)
    delivery_address = models.CharField(max_length=255)
    delivery_city = models.CharField(max_length=100)
    delivery_pincode = models.CharField(max_length=12)
    payment_method = models.CharField(max_length=20, choices=Order.PAYMENT_CHOICES, default=Order.PAYMENT_COD)
    last_order = models.ForeignKey(
        Order, related_name="source_subscriptions", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_frequency_display()} subscription #{self.id}"


class SubscriptionItem(models.Model):
    subscription = models.ForeignKey(Subscription, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Coupon(models.Model):
    code = models.CharField(max_length=30, unique=True)
    discount_percent = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="cart", on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart({self.user})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("cart", "product")

    def __str__(self):
        return f"{self.product} x {self.quantity}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="profile", on_delete=models.CASCADE
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    pincode = models.CharField(max_length=12, blank=True)
    email_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile({self.user.username})"


class PaymentTransaction(models.Model):
    STATUS_INITIATED = "initiated"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_INITIATED, "Initiated"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    )

    order = models.ForeignKey(Order, related_name="payments", on_delete=models.CASCADE)
    provider = models.CharField(max_length=20, choices=Order.PAYMENT_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIATED)
    reference = models.CharField(max_length=64, unique=True)
    provider_payment_id = models.CharField(max_length=120, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def mark_success(self, provider_payment_id="", gateway_response=None):
        self.status = self.STATUS_SUCCESS
        self.provider_payment_id = provider_payment_id
        self.failure_reason = ""
        self.gateway_response = gateway_response or {}
        self.paid_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "provider_payment_id",
                "failure_reason",
                "gateway_response",
                "paid_at",
                "updated_at",
            ]
        )
        self.order.payment_status = Order.PAYMENT_PAID
        self.order.save(update_fields=["payment_status"])

    def mark_failed(self, reason="", gateway_response=None):
        self.status = self.STATUS_FAILED
        self.failure_reason = reason
        self.gateway_response = gateway_response or {}
        self.paid_at = None
        self.save(update_fields=["status", "failure_reason", "gateway_response", "paid_at", "updated_at"])
        self.order.payment_status = Order.PAYMENT_FAILED
        self.order.save(update_fields=["payment_status"])

    def __str__(self):
        return f"{self.get_provider_display()} payment #{self.reference}"
