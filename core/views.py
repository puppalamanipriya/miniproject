from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote_plus

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import EmailOrUsernameAuthenticationForm, ProfileForm, SignUpForm
from .models import (
    Cart,
    CartItem,
    Category,
    Coupon,
    Order,
    OrderItem,
    Product,
    Subscription,
    SubscriptionItem,
    UserProfile,
)

SESSION_CART_KEY = "cart_items"


def _safe_int(value, default=1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _get_cart(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    return cart


def _get_session_cart(request):
    raw_cart = request.session.get(SESSION_CART_KEY, {})
    cleaned_cart = {}
    for product_id, quantity in raw_cart.items():
        quantity = _safe_int(quantity, default=0)
        if quantity > 0:
            cleaned_cart[str(product_id)] = quantity
    if cleaned_cart != raw_cart:
        request.session[SESSION_CART_KEY] = cleaned_cart
    return cleaned_cart


def _set_session_cart(request, cart_data):
    request.session[SESSION_CART_KEY] = cart_data
    request.session.modified = True


def _cart_count(request):
    if request.user.is_authenticated:
        cart = _get_cart(request)
        return sum(item.quantity for item in cart.items.all())
    return sum(_get_session_cart(request).values())


def _cart_details(request):
    if request.user.is_authenticated:
        cart = _get_cart(request)
        entries = cart.items.select_related("product")
        return _build_cart_details([(entry.product, entry.quantity) for entry in entries])
    session_cart = _get_session_cart(request)
    products = Product.objects.in_bulk(session_cart.keys())
    product_quantity_pairs = []
    for product_id, quantity in session_cart.items():
        product = products.get(int(product_id))
        if not product:
            continue
        product_quantity_pairs.append((product, quantity))
    return _build_cart_details(product_quantity_pairs)


def _build_cart_details(product_quantity_pairs):
    items = []
    total = Decimal("0.00")
    for product, quantity in product_quantity_pairs:
        subtotal = product.price * quantity
        total += subtotal
        items.append(
            {
                "product": product,
                "quantity": quantity,
                "subtotal": subtotal,
            }
        )
    return items, total


def _merge_session_cart_to_user_cart(request):
    if not request.user.is_authenticated:
        return
    session_cart = _get_session_cart(request)
    if not session_cart:
        return
    cart = _get_cart(request)
    products = Product.objects.in_bulk(session_cart.keys())
    for product_id, quantity in session_cart.items():
        product = products.get(int(product_id))
        if not product:
            continue
        item, _ = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": 0})
        item.quantity = min(item.quantity + quantity, product.stock_quantity)
        item.save(update_fields=["quantity"])
    _set_session_cart(request, {})


def _full_delivery_address(order):
    parts = [order.delivery_address, order.delivery_city, order.delivery_pincode]
    return ", ".join(part for part in parts if part)


def _maps_search_link(query):
    return f"https://www.google.com/maps?q={quote_plus(query)}"


def _maps_directions_link(origin, destination):
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={quote_plus(origin)}&destination={quote_plus(destination)}"
    )


def _tracking_snapshot(order):
    status_map = {
        Order.STATUS_PLACED: ("Placed", 25),
        Order.STATUS_PACKED: ("Packed", 45),
        Order.STATUS_OUT_FOR_DELIVERY: ("Out For Delivery", 75),
        Order.STATUS_DELIVERED: ("Delivered", 100),
        Order.STATUS_CANCELLED: ("Cancelled", 100),
    }
    status_label, progress = status_map.get(order.tracking_status, ("Placed", 25))
    destination = _full_delivery_address(order) or "Customer Delivery Address"
    location = order.current_location or destination
    return {
        "status": status_label,
        "location": location,
        "location_query": location,
        "progress": progress,
    }


def _safe_next_url(request, default="home"):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse(default)


def _send_verification_email(request, user):
    signer = TimestampSigner(salt="watersupply-email-verify")
    token = signer.sign(str(user.pk))
    link = request.build_absolute_uri(reverse("verify_email", args=[token]))
    send_mail(
        subject="Verify your WaterSupply account email",
        message=f"Click to verify your account: {link}",
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@watersupply.local"),
        recipient_list=[user.email],
        fail_silently=True,
    )


def home(request):
    cart_count = _cart_count(request)
    latest_orders = []
    if request.user.is_authenticated:
        latest_orders = request.user.orders.prefetch_related("items__product")[:3]
    featured_products = Product.objects.filter(is_featured=True)[:6]
    return render(
        request,
        "core/home.html",
        {
            "featured_products": featured_products,
            "total_products": Product.objects.count(),
            "cart_count": cart_count,
            "latest_orders": latest_orders,
        },
    )


@login_required
def profile_page(request):
    profile = _get_profile(request.user)
    form = ProfileForm(request.POST or None, instance=profile, user=request.user)
    for field in form.fields.values():
        field.widget.attrs.update({"class": "form-control"})

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("profile")
        messages.error(request, "Please correct the errors below.")

    return render(request, "core/profile.html", {"form": form, "cart_count": _cart_count(request)})


def shop(request):
    cart_count = _cart_count(request)
    products = Product.objects.select_related("category").all()
    categories = Category.objects.all()

    query = (request.GET.get("q") or "").strip()
    category_slug = (request.GET.get("category") or "").strip()
    sort = (request.GET.get("sort") or "").strip()

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(volume_label__icontains=query)
        )
    if category_slug:
        products = products.filter(category__slug=category_slug)

    sort_map = {
        "price_asc": "price",
        "price_desc": "-price",
        "name_asc": "name",
        "stock_desc": "-stock_quantity",
    }
    if sort in sort_map:
        products = products.order_by(sort_map[sort])

    return render(
        request,
        "core/shop.html",
        {
            "products": products,
            "categories": categories,
            "query": query,
            "selected_category": category_slug,
            "selected_sort": sort,
            "cart_count": cart_count,
        },
    )


def product_detail(request, product_id):
    cart_count = _cart_count(request)
    product = get_object_or_404(Product, id=product_id)
    return render(
        request,
        "core/product_detail.html",
        {"product": product, "cart_count": cart_count},
    )


def cart_page(request):
    cart_items, cart_total = _cart_details(request)
    return render(
        request,
        "core/cart.html",
        {"cart_items": cart_items, "cart_total": cart_total, "cart_count": _cart_count(request)},
    )


@login_required
def orders_page(request):
    orders = request.user.orders.prefetch_related("items__product")
    order_cards = []
    for order in orders:
        tracking = _tracking_snapshot(order)
        destination = _full_delivery_address(order)
        order_cards.append(
            {
                "order": order,
                "tracking": tracking,
                "map_link": _maps_search_link(tracking["location_query"]),
                "delivery_map_link": _maps_search_link(destination),
            }
        )
    return render(
        request,
        "core/orders.html",
        {"order_cards": order_cards, "cart_count": _cart_count(request)},
    )


@login_required
def subscriptions_page(request):
    subscriptions = request.user.subscriptions.prefetch_related("items__product")
    return render(
        request,
        "core/subscriptions.html",
        {"subscriptions": subscriptions, "cart_count": _cart_count(request)},
    )


@login_required
def track_order_page(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        id=order_id,
        user=request.user,
    )
    tracking = _tracking_snapshot(order)
    destination = _full_delivery_address(order)
    origin = "WaterSupply Warehouse Bengaluru"
    return render(
        request,
        "core/track_order.html",
        {
            "order": order,
            "tracking": tracking,
            "map_link": _maps_search_link(tracking["location_query"]),
            "delivery_map_link": _maps_search_link(destination),
            "route_map_link": _maps_directions_link(origin, destination),
            "cart_count": _cart_count(request),
        },
    )


@login_required
def about_page(request):
    return render(request, "core/about.html", {"cart_count": _cart_count(request)})


@login_required
def contact_page(request):
    return render(request, "core/contact.html", {"cart_count": _cart_count(request)})


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    requested_quantity = max(1, _safe_int(request.POST.get("quantity", 1), default=1))

    if request.user.is_authenticated:
        cart = _get_cart(request)
        item, _ = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": 0})
        new_quantity = item.quantity + requested_quantity
        if new_quantity > product.stock_quantity:
            messages.error(request, f"Only {product.stock_quantity} unit(s) available for {product.name}.")
            return redirect(request.POST.get("next", "shop"))
        item.quantity = new_quantity
        item.save(update_fields=["quantity"])
    else:
        session_cart = _get_session_cart(request)
        current_quantity = session_cart.get(str(product.id), 0)
        new_quantity = current_quantity + requested_quantity
        if new_quantity > product.stock_quantity:
            messages.error(request, f"Only {product.stock_quantity} unit(s) available for {product.name}.")
            return redirect(request.POST.get("next", "shop"))
        session_cart[str(product.id)] = new_quantity
        _set_session_cart(request, session_cart)

    messages.success(request, f"Added {requested_quantity} x {product.name} {product.volume_label}.")
    return redirect(request.POST.get("next", "shop"))


@require_POST
def update_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    quantity = _safe_int(request.POST.get("quantity", 1), default=1)

    if quantity > product.stock_quantity:
        messages.error(request, f"Cannot exceed stock. Available: {product.stock_quantity}.")
        return redirect("cart")

    if request.user.is_authenticated:
        cart = _get_cart(request)
        item = CartItem.objects.filter(cart=cart, product=product).first()
        if not item:
            return redirect("cart")
        if quantity <= 0:
            item.delete()
            messages.info(request, f"Removed {product.name} from cart.")
        else:
            item.quantity = quantity
            item.save(update_fields=["quantity"])
            messages.success(request, f"Updated quantity for {product.name}.")
    else:
        session_cart = _get_session_cart(request)
        key = str(product.id)
        if key not in session_cart:
            return redirect("cart")
        if quantity <= 0:
            session_cart.pop(key, None)
            messages.info(request, f"Removed {product.name} from cart.")
        else:
            session_cart[key] = quantity
            messages.success(request, f"Updated quantity for {product.name}.")
        _set_session_cart(request, session_cart)
    return redirect("cart")


@require_POST
def remove_from_cart(request, product_id):
    if request.user.is_authenticated:
        cart = _get_cart(request)
        CartItem.objects.filter(cart=cart, product_id=product_id).delete()
    else:
        session_cart = _get_session_cart(request)
        session_cart.pop(str(product_id), None)
        _set_session_cart(request, session_cart)
    return redirect("cart")


@require_POST
@login_required
@transaction.atomic
def checkout(request):
    cart = _get_cart(request)
    cart_items, cart_subtotal = _cart_details(request)
    if not cart_items:
        messages.error(request, "Your cart is empty.")
        return redirect("cart")

    delivery_name = (request.POST.get("delivery_name") or "").strip()
    delivery_phone = (request.POST.get("delivery_phone") or "").strip()
    delivery_address = (request.POST.get("delivery_address") or "").strip()
    delivery_city = (request.POST.get("delivery_city") or "").strip()
    delivery_pincode = (request.POST.get("delivery_pincode") or "").strip()
    coupon_code = (request.POST.get("coupon_code") or "").strip().upper()
    payment_method = request.POST.get("payment_method") or Order.PAYMENT_COD
    fulfillment_type = request.POST.get("fulfillment_type") or Order.FULFILLMENT_ONE_TIME

    allowed_fulfillment_types = {
        Order.FULFILLMENT_ONE_TIME,
        Order.FULFILLMENT_WEEKLY,
        Order.FULFILLMENT_MONTHLY,
    }
    if fulfillment_type not in allowed_fulfillment_types:
        fulfillment_type = Order.FULFILLMENT_ONE_TIME

    if not all([delivery_name, delivery_phone, delivery_address, delivery_city, delivery_pincode]):
        messages.error(request, "Please provide complete delivery address details.")
        return redirect("cart")

    discount_amount = Decimal("0.00")
    if coupon_code:
        now = timezone.now()
        coupon = (
            Coupon.objects.filter(
                code__iexact=coupon_code, is_active=True, valid_from__lte=now, valid_to__gte=now
            )
            .order_by("-id")
            .first()
        )
        if not coupon:
            messages.error(request, "Invalid or expired coupon code.")
            return redirect("cart")
        if cart_subtotal < coupon.minimum_order_amount:
            messages.error(request, f"Coupon requires minimum order amount Rs. {coupon.minimum_order_amount}.")
            return redirect("cart")
        discount_amount = (cart_subtotal * Decimal(coupon.discount_percent) / Decimal("100")).quantize(
            Decimal("0.01")
        )

    total = (cart_subtotal - discount_amount).quantize(Decimal("0.01"))
    payment_status = Order.PAYMENT_PENDING if payment_method != Order.PAYMENT_COD else Order.PAYMENT_PENDING

    order = Order.objects.create(
        user=request.user,
        total_amount=total,
        subtotal_amount=cart_subtotal,
        discount_amount=discount_amount,
        delivery_name=delivery_name,
        delivery_phone=delivery_phone,
        delivery_address=delivery_address,
        delivery_city=delivery_city,
        delivery_pincode=delivery_pincode,
        tracking_status=Order.STATUS_PLACED,
        current_location="WaterSupply Warehouse",
        tracking_latitude=Decimal("12.971600"),
        tracking_longitude=Decimal("77.594600"),
        payment_method=payment_method,
        payment_status=payment_status,
        fulfillment_type=fulfillment_type,
        coupon_code=coupon_code,
        invoice_number=f"INV-{timezone.now().strftime('%Y%m%d')}-{request.user.id}-{int(timezone.now().timestamp())}",
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                unit_price=item["product"].price,
            )
            for item in cart_items
        ]
    )

    CartItem.objects.filter(cart=cart).delete()
    if fulfillment_type in (Order.FULFILLMENT_WEEKLY, Order.FULFILLMENT_MONTHLY):
        start_date = timezone.localdate()
        delta_days = 7 if fulfillment_type == Order.FULFILLMENT_WEEKLY else 30
        subscription = Subscription.objects.create(
            user=request.user,
            frequency=fulfillment_type,
            status=Subscription.STATUS_ACTIVE,
            start_date=start_date,
            next_delivery_date=start_date + timedelta(days=delta_days),
            delivery_name=delivery_name,
            delivery_phone=delivery_phone,
            delivery_address=delivery_address,
            delivery_city=delivery_city,
            delivery_pincode=delivery_pincode,
            payment_method=payment_method,
            last_order=order,
        )
        SubscriptionItem.objects.bulk_create(
            [
                SubscriptionItem(
                    subscription=subscription,
                    product=item["product"],
                    quantity=item["quantity"],
                    unit_price=item["product"].price,
                )
                for item in cart_items
            ]
        )
        messages.success(
            request,
            f"{subscription.get_frequency_display()} subscription #{subscription.id} started.",
        )
    if payment_method in (Order.PAYMENT_RAZORPAY, Order.PAYMENT_STRIPE):
        messages.info(
            request,
            f"{dict(Order.PAYMENT_CHOICES).get(payment_method)} integration requires API keys. "
            "Order created in pending payment state.",
        )
    messages.success(request, f"Order #{order.id} placed successfully.")
    return redirect("orders")


@require_POST
@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.tracking_status in (Order.STATUS_DELIVERED, Order.STATUS_CANCELLED):
        messages.error(request, "This order cannot be cancelled.")
        return redirect("orders")
    order.tracking_status = Order.STATUS_CANCELLED
    order.cancel_reason = (request.POST.get("cancel_reason") or "").strip()
    order.save(update_fields=["tracking_status", "cancel_reason"])
    messages.success(request, f"Order #{order.id} cancelled.")
    return redirect("orders")


@require_POST
@login_required
def request_return(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.tracking_status != Order.STATUS_DELIVERED:
        messages.error(request, "Returns are allowed only for delivered orders.")
        return redirect("orders")
    order.is_return_requested = True
    order.return_reason = (request.POST.get("return_reason") or "").strip()
    order.save(update_fields=["is_return_requested", "return_reason"])
    messages.success(request, f"Return request sent for order #{order.id}.")
    return redirect("orders")


@require_POST
@login_required
def update_subscription_status(request, subscription_id):
    subscription = get_object_or_404(Subscription, id=subscription_id, user=request.user)
    new_status = request.POST.get("status")
    allowed_statuses = {
        Subscription.STATUS_ACTIVE,
        Subscription.STATUS_PAUSED,
        Subscription.STATUS_CANCELLED,
    }
    if new_status not in allowed_statuses:
        messages.error(request, "Invalid subscription status.")
        return redirect("/subscriptions/")
    subscription.status = new_status
    subscription.save(update_fields=["status"])
    messages.success(request, f"Subscription #{subscription.id} updated to {subscription.get_status_display()}.")
    return redirect("/subscriptions/")


def login_page(request):
    if request.user.is_authenticated:
        return redirect(_safe_next_url(request, default="home"))
    form = EmailOrUsernameAuthenticationForm(request, data=request.POST or None)
    form.fields["username"].widget.attrs.update(
        {"class": "form-control", "placeholder": "Enter username or email"}
    )
    form.fields["password"].widget.attrs.update({"class": "form-control", "placeholder": "Enter password"})

    if request.method == "POST":
        if form.is_valid():
            auth_login(request, form.get_user())
            _merge_session_cart_to_user_cart(request)
            messages.success(request, "You have been logged in successfully.")
            return redirect(_safe_next_url(request, default="home"))
        messages.error(request, "Invalid username or password.")

    return render(request, "core/login.html", {"form": form, "next": request.GET.get("next", "")})


def signup_page(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = SignUpForm(request.POST or None)
    for field_name in ("username", "email", "password1", "password2"):
        form.fields[field_name].widget.attrs.update({"class": "form-control"})

    if request.method == "POST":
        if form.is_valid():
            user = form.save()
            _get_profile(user)
            _send_verification_email(request, user)
            messages.success(
                request,
                "Account created successfully. Please log in to continue.",
            )
            return redirect("login")
        messages.error(request, "Please fix the errors below.")
    return render(request, "core/signup.html", {"form": form})


def verify_email(request, token):
    signer = TimestampSigner(salt="watersupply-email-verify")
    try:
        user_id = signer.unsign(token, max_age=60 * 60 * 24)
    except (BadSignature, SignatureExpired):
        messages.error(request, "Verification link is invalid or expired.")
        return redirect("profile")

    user = get_object_or_404(User, pk=user_id)
    profile = _get_profile(user)
    profile.email_verified = True
    profile.save(update_fields=["email_verified"])
    messages.success(request, "Email verified successfully.")
    return redirect("profile")


@require_POST
@login_required
def resend_verification_email(request):
    profile = _get_profile(request.user)
    if profile.email_verified:
        messages.info(request, "Your email is already verified.")
        return redirect("profile")
    if not request.user.email:
        messages.error(request, "Add an email address in your profile before verifying.")
        return redirect("profile")
    _send_verification_email(request, request.user)
    messages.success(request, "Verification email sent. Check your inbox or server console output.")
    return redirect("profile")


@login_required
def logout_confirm_page(request):
    return render(request, "core/logout_confirm.html", {"cart_count": _cart_count(request)})


@require_POST
def logout_page(request):
    if not request.user.is_authenticated:
        messages.info(request, "You are already logged out.")
        return redirect("login")
    auth_logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")
