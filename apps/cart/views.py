from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from apps.catalog.models import Product
from .services import Cart


class CartDetailView(TemplateView):
    template_name = "cart/cart_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        cart = Cart(self.request)

        context["cart"] = cart
        context["items"] = list(cart)
        context["total"] = cart.get_total_price()

        return context


class CartAddView(View):
    def post(self, request, product_id):
        product = get_object_or_404(
            Product,
            pk=product_id,
            is_active=True,
            category__is_active=True,
        )

        try:
            quantity = int(request.POST.get("quantity", 1))

            if quantity < 1:
                raise ValueError("La cantidad debe ser mayor que cero.")

            cart = Cart(request)
            cart.add(product, quantity)

        except ValueError as error:
            messages.error(request, str(error))
        else:
            messages.success(
                request,
                "Producto añadido al carrito.",
            )

        return redirect("cart:detail")


class CartRemoveView(View):
    def post(self, request, product_id):
        cart = Cart(request)
        cart.remove(product_id)

        messages.success(
            request,
            "Producto eliminado del carrito.",
        )

        return redirect("cart:detail")
