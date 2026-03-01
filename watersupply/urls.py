"""
URL configuration for watersupply project.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]

handler404 = "core.error_views.custom_404"
handler500 = "core.error_views.custom_500"
