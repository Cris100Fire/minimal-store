from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("cart/", include("apps.cart.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("orders/", include("apps.orders.urls")),
]
