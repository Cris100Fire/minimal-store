from decimal import Decimal
from django.db import transaction

from apps.catalog.models import Product
from .models import Order, OrderItem


@transaction.atomic
def create_order(*, user, cart):
    cart_items = cart.cart

    if not cart_items:
        raise ValueError("Tu carrito está vacío.")

    product_ids = []

    for product_id, quantity in cart_items.items():
        if (
            not isinstance(product_id, str)
            or not product_id.isdigit()
            or not isinstance(quantity, int)
            or isinstance(quantity, bool)
            or quantity < 1
        ):
            raise ValueError("El carrito contiene datos inválidos.")

        product_ids.append(int(product_id))

    products = Product.objects.select_for_update().filter(
        pk__in=product_ids,
        is_active=True,
        category__is_active=True,
    )

    products_by_id = {str(product.pk): product for product in products}

    if len(products_by_id) != len(cart_items):
        raise ValueError(
            "Uno o más productos ya no están disponibles. " "Revisa tu carrito."
        )

    order_lines = []
    total = Decimal("0.00")

    for product_id, quantity in cart_items.items():
        product = products_by_id[product_id]

        if product.stock < quantity:
            raise ValueError(
                f"No hay suficiente stock de {product.name}. "
                f"Unidades disponibles: {product.stock}."
            )

        unit_price = product.price
        subtotal = unit_price * quantity
        total += subtotal

        order_lines.append(
            {
                "product": product,
                "product_name": product.name,
                "unit_price": unit_price,
                "quantity": quantity,
            }
        )

    order = Order.objects.create(
        user=user,
        status=Order.Status.PENDING,
        total=total,
    )

    OrderItem.objects.bulk_create(
        [OrderItem(order=order, **line) for line in order_lines]
    )

    for line in order_lines:
        product = line["product"]
        product.stock -= line["quantity"]
        product.save(update_fields=["stock", "updated_at"])

    return order


@transaction.atomic
def cancel_order(*, order_id):
    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist:
        raise ValueError("El pedido no existe.")

    if order.status == Order.Status.CANCELLED:
        raise ValueError("Este pedido ya está cancelado.")

    if order.status != Order.Status.PENDING:
        raise ValueError("Solo se pueden cancelar pedidos pendientes.")

    items = list(OrderItem.objects.filter(order=order).order_by("product_id"))

    if not items:
        raise ValueError("El pedido no tiene productos y no puede cancelarse.")

    product_ids = {item.product.pk for item in items}

    products = (
        Product.objects.select_for_update().filter(pk__in=product_ids).order_by("pk")
    )

    products_by_id = {product.pk: product for product in products}

    if len(products_by_id) != len(product_ids):
        raise ValueError("No se encontraron todos los productos del pedido.")

    # Restituir las cantidades al inventario.
    for item in items:
        product = products_by_id[item.product.pk]
        product.stock += item.quantity
        product.save(update_fields=["stock", "updated_at"])

    # Marcar el pedido como cancelado.
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    return order


def validate_order_status_transition(*, current_status: str, new_status: str):
    valid_statuses = Order.Status.values

    if new_status not in valid_statuses:
        raise ValueError("El estado indicado no es válido.")

    if current_status == new_status:
        return

    if new_status == Order.Status.CANCELLED:
        if current_status != Order.Status.PENDING:
            raise ValueError("Solo se pueden cancelar pedidos pendientes.")
        return

    allowed_transitions: dict[str, set[str]] = {
        Order.Status.PENDING: {Order.Status.PAID},
        Order.Status.PAID: {Order.Status.SHIPPED},
        Order.Status.SHIPPED: {Order.Status.DELIVERED},
        Order.Status.DELIVERED: set(),
        Order.Status.CANCELLED: set(),
    }

    permitted = allowed_transitions.get(current_status, set())

    if new_status not in permitted:
        status_labels = dict(Order.Status.choices)

        raise ValueError(
            f"No se permite cambiar un pedido de "
            f"{status_labels.get(current_status, current_status)} a "
            f"{status_labels[new_status]}."
        )


@transaction.atomic
def transition_order_status(*, order_id, new_status):
    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist:
        raise ValueError("El pedido no existe.")

    validate_order_status_transition(
        current_status=order.status,
        new_status=new_status,
    )

    if order.status == new_status:
        return order

    if new_status == Order.Status.CANCELLED:
        return cancel_order(order_id=order_id)

    order.status = new_status
    order.save(update_fields=["status", "updated_at"])

    return order
