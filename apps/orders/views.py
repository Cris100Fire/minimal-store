from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import DetailView, TemplateView, ListView

from apps.cart.services import Cart
from .models import Order
from .services import create_order


class CheckoutView(LoginRequiredMixin, TemplateView):
    template_name = "orders/checkout.html"
    login_url = "accounts:login"

    def get(self, request, *args, **kwargs):
        cart = Cart(request)

        if len(cart) == 0:
            messages.warning(request, "Tu carrito está vacío.")
            return redirect("cart:detail")

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = Cart(self.request)

        context["items"] = list(cart)
        context["total"] = cart.get_total_price()

        return context

    def post(self, request, *args, **kwargs):
        cart = Cart(request)

        try:
            order = create_order(user=request.user, cart=cart)
        except ValueError as error:
            messages.error(request, str(error))
            return redirect("orders:checkout")

        cart.clear()

        return redirect(
            "orders:confirmation",
            pk=order.pk,
        )


class OrderConfirmationView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = "orders/confirmation.html"
    context_object_name = "order"
    login_url = "accounts:login"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")


class OrdersView(LoginRequiredMixin, ListView):
    model = Order
    template_name = "orders/orders_history.html"
    context_object_name = "orders"
    login_url = "accounts:login"
    paginate_by = 10

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by("-created_at")
