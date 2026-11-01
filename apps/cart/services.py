from decimal import Decimal

from apps.catalog.models import Product


class Cart:
    SESSION_KEY = "cart"

    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.get(self.SESSION_KEY, {})

        if not isinstance(self.cart, dict):
            self.cart = {}

    def save(self):
        self.session[self.SESSION_KEY] = self.cart
        self.session.modified = True

    def add(self, product, quantity=1, override_quantity=False):
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise ValueError("La cantidad debe ser un número entero.")

        if quantity < 1:
            raise ValueError("La cantidad debe ser mayor que cero.")

        if not product.is_active or not product.category.is_active:
            raise ValueError("Este producto no está disponible.")

        product_id = str(product.pk)
        current_quantity = self.cart.get(product_id, 0)

        if not isinstance(current_quantity, int) or isinstance(current_quantity, bool):
            current_quantity = 0

        new_quantity = quantity if override_quantity else current_quantity + quantity

        if new_quantity > product.stock:
            raise ValueError("La cantidad solicitada supera el stock disponible.")

        self.cart[product_id] = new_quantity
        self.save()

    def remove(self, product_id):
        product_id = str(product_id)

        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def clear(self):
        self.session.pop(self.SESSION_KEY, None)
        self.session.modified = True
        self.cart = {}

    def __iter__(self):
        valid_product_ids = [
            product_id
            for product_id in self.cart
            if isinstance(product_id, str) and product_id.isdecimal()
        ]

        products = Product.objects.filter(
            pk__in=valid_product_ids,
            is_active=True,
            category__is_active=True,
        ).select_related("category")

        products_by_id = {str(product.pk): product for product in products}

        for product_id, quantity in self.cart.items():
            product = products_by_id.get(product_id)

            if product is None:
                continue

            if (
                not isinstance(quantity, int)
                or isinstance(quantity, bool)
                or quantity < 1
            ):
                continue

            subtotal = product.price * quantity

            yield {
                "product": product,
                "quantity": quantity,
                "unit_price": product.price,
                "subtotal": subtotal,
            }

    def __len__(self):
        return sum(item["quantity"] for item in self)

    def get_total_price(self):
        return sum((item["subtotal"] for item in self), Decimal("0.00"))
