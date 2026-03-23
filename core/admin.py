from django.contrib import admin

from .models import (
    Cart,
    CartItem,
    Category,
    Coupon,
    Order,
    OrderItem,
    PaymentTransaction,
    Product,
    Subscription,
    SubscriptionItem,
    UserProfile,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price")


class SubscriptionItemInline(admin.TabularInline):
    model = SubscriptionItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "volume_label",
        "price",
        "stock_quantity",
        "low_stock_threshold",
        "is_featured",
    )
    list_filter = ("is_featured", "category")
    search_fields = ("name", "volume_label", "category__name")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "delivery_name",
        "delivery_city",
        "tracking_status",
        "payment_status",
        "payment_method",
        "fulfillment_type",
        "current_location",
        "created_at",
        "total_amount",
    )
    list_filter = ("tracking_status", "delivery_city", "payment_status", "payment_method")
    search_fields = (
        "delivery_name",
        "delivery_phone",
        "delivery_address",
        "delivery_city",
        "invoice_number",
    )
    inlines = [OrderItemInline]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "frequency",
        "status",
        "next_delivery_date",
        "delivery_city",
        "created_at",
    )
    list_filter = ("frequency", "status", "delivery_city")
    search_fields = ("delivery_name", "delivery_phone", "delivery_address", "delivery_city")
    inlines = [SubscriptionItemInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_percent", "is_active", "valid_from", "valid_to")
    list_filter = ("is_active",)
    search_fields = ("code",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "city", "email_verified")
    list_filter = ("email_verified", "city")
    search_fields = ("user__username", "user__email", "phone", "city")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "product", "quantity")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "order", "provider", "status", "amount", "provider_payment_id", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("reference", "provider_payment_id", "order__invoice_number")
