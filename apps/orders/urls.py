from django.urls import path

from .views import CheckoutView, OrderConfirmationView, OrdersView

app_name = "orders"

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path(
        "my-orders/",
        OrdersView.as_view(),
        name="my_orders",
    ),
    path(
        "<int:pk>/confirmation/",
        OrderConfirmationView.as_view(),
        name="confirmation",
    ),
]
