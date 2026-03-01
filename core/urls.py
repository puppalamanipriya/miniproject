from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.signup_page, name="landing"),
    path("home/", views.home, name="home"),
    path("profile/", views.profile_page, name="profile"),
    path("verify-email/<str:token>/", views.verify_email, name="verify_email"),
    path("verify-email/resend/", views.resend_verification_email, name="resend_verification_email"),
    path("shop/", views.shop, name="shop"),
    path("products/<int:product_id>/", views.product_detail, name="product_detail"),
    path("cart/", views.cart_page, name="cart"),
    path("orders/", views.orders_page, name="orders"),
    path("subscriptions/", views.subscriptions_page, name="subscriptions"),
    path("orders/<int:order_id>/track/", views.track_order_page, name="track_order"),
    path("about/", views.about_page, name="about"),
    path("contact/", views.contact_page, name="contact"),
    path("add-to-cart/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("update-cart/<int:product_id>/", views.update_cart, name="update_cart"),
    path("remove-from-cart/<int:product_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/<int:order_id>/cancel/", views.cancel_order, name="cancel_order"),
    path("orders/<int:order_id>/return/", views.request_return, name="request_return"),
    path(
        "subscriptions/<int:subscription_id>/status/",
        views.update_subscription_status,
        name="update_subscription_status",
    ),
    path("login/", views.login_page, name="login"),
    path("signup/", views.signup_page, name="signup"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html"
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("logout/confirm/", views.logout_confirm_page, name="logout_confirm"),
    path("logout/", views.logout_page, name="logout"),
]
