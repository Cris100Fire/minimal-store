from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
import threading
from queue import Queue

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.contrib import admin
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from apps.catalog.models import Category, Product
from .models import Order, OrderItem
from .services import cancel_order, create_order, transition_order_status
from .admin import OrderAdmin, OrderAdminForm, OrderItemInline

User = get_user_model()


class OrderServiceTests(TestCase):
    def setUp(self):
        """Prepara los datos comunes de cada prueba."""
        self.user = User.objects.create_user(
            username="cliente_test",
            password="test-password-123",
        )

        self.category = Category.objects.create(
            name="Categoría de prueba",
            slug="categoria-prueba",
        )

        self.product = Product.objects.create(
            category=self.category,
            name="Producto de prueba",
            slug="producto-prueba",
            price=Decimal("25.00"),
            stock=10,
        )

    def make_cart(self, quantity):
        """Construye un carrito sencillo para probar el servicio."""
        return SimpleNamespace(cart={str(self.product.pk): quantity})

    def test_create_order_decreases_stock_and_calculates_total(self):
        order = create_order(
            user=self.user,
            cart=self.make_cart(2),
        )

        self.product.refresh_from_db()

        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.total, Decimal("50.00"))
        self.assertEqual(self.product.stock, 8)
        self.assertEqual(order.items.count(), 1)

    def test_cancel_pending_order_restores_stock(self):
        order = create_order(
            user=self.user,
            cart=self.make_cart(2),
        )

        cancel_order(order_id=order.pk)

        order.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.product.stock, 10)

    def test_cancelling_twice_does_not_restore_stock_twice(self):
        order = create_order(
            user=self.user,
            cart=self.make_cart(2),
        )

        cancel_order(order_id=order.pk)

        with self.assertRaisesMessage(
            ValueError,
            "Este pedido ya está cancelado.",
        ):
            cancel_order(order_id=order.pk)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_paid_order_cannot_be_cancelled(self):
        order = create_order(
            user=self.user,
            cart=self.make_cart(2),
        )

        order.status = Order.Status.PAID
        order.save(update_fields=["status"])

        with self.assertRaisesMessage(
            ValueError,
            "Solo se pueden cancelar pedidos pendientes.",
        ):
            cancel_order(order_id=order.pk)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_insufficient_stock_does_not_create_order(self):
        with self.assertRaisesMessage(
            ValueError,
            "No hay suficiente stock",
        ):
            create_order(
                user=self.user,
                cart=self.make_cart(11),
            )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock, 10)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_empty_cart_does_not_create_order(self):
        with self.assertRaisesMessage(
            ValueError,
            "Tu carrito está vacío.",
        ):
            create_order(
                user=self.user,
                cart=SimpleNamespace(cart={}),
            )

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_inactive_product_does_not_create_order(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        with self.assertRaisesMessage(
            ValueError,
            "Uno o más productos ya no están disponibles.",
        ):
            create_order(
                user=self.user,
                cart=self.make_cart(1),
            )

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_inactive_category_does_not_create_order(self):
        self.category.is_active = False
        self.category.save(update_fields=["is_active"])

        with self.assertRaisesMessage(
            ValueError,
            "Uno o más productos ya no están disponibles.",
        ):
            create_order(
                user=self.user,
                cart=self.make_cart(1),
            )

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_cancelling_nonexistent_order_raises_error(self):
        nonexistent_order_id = 999999

        with self.assertRaisesMessage(
            ValueError,
            "El pedido no existe.",
        ):
            cancel_order(order_id=nonexistent_order_id)

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_cannot_cancel_order_without_items(self):
        order = Order.objects.create(
            user=self.user,
            status=Order.Status.PENDING,
            total=Decimal("0.00"),
        )

        with self.assertRaisesMessage(
            ValueError,
            "El pedido no tiene productos y no puede cancelarse.",
        ):
            cancel_order(order_id=order.pk)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_order_item_preserves_product_name_and_price_snapshot(self):
        order = create_order(
            user=self.user,
            cart=self.make_cart(2),
        )

        item = order.items.get()

        # Modificamos el producto después de crear el pedido.
        self.product.name = "Nombre actualizado"
        self.product.price = Decimal("99.00")
        self.product.save(update_fields=["name", "price"])

        # El detalle del pedido debe conservar los datos originales.
        item.refresh_from_db()

        self.assertEqual(item.product_name, "Producto de prueba")
        self.assertEqual(item.unit_price, Decimal("25.00"))
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.subtotal, Decimal("50.00"))

        # El total histórico del pedido tampoco debe cambiar.
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal("50.00"))

    def test_order_with_multiple_products_calculates_total_and_updates_stock(self):
        second_product = Product.objects.create(
            category=self.category,
            name="Segundo producto",
            slug="segundo-producto",
            price=Decimal("10.50"),
            stock=8,
        )

        cart = SimpleNamespace(
            cart={
                str(self.product.pk): 2,
                str(second_product.pk): 3,
            }
        )

        order = create_order(user=self.user, cart=cart)

        self.product.refresh_from_db()
        second_product.refresh_from_db()

        self.assertEqual(order.total, Decimal("81.50"))
        self.assertEqual(order.items.count(), 2)

        self.assertEqual(self.product.stock, 8)
        self.assertEqual(second_product.stock, 5)

        self.assertEqual(
            order.items.get(product=self.product).subtotal,
            Decimal("50.00"),
        )
        self.assertEqual(
            order.items.get(product=second_product).subtotal,
            Decimal("31.50"),
        )

        self.assertEqual(
            sum(
                (item.subtotal for item in order.items.all()),
                Decimal("0.00"),
            ),
            order.total,
        )

    def test_invalid_cart_data_does_not_create_order(self):
        invalid_carts = [
            {"abc": 1},  # ID de producto no numérico.
            {str(self.product.pk): 0},  # Cantidad cero.
            {str(self.product.pk): -1},  # Cantidad negativa.
            {str(self.product.pk): True},  # Booleano, no entero válido.
        ]

        for cart_data in invalid_carts:
            with self.subTest(cart_data=cart_data):
                with self.assertRaisesMessage(
                    ValueError,
                    "El carrito contiene datos inválidos.",
                ):
                    create_order(
                        user=self.user,
                        cart=SimpleNamespace(cart=cart_data),
                    )

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_cancel_order_fails_if_a_product_is_missing(self):
        order = create_order(
            user=self.user,
            cart=self.make_cart(2),
        )

        with patch(
            "apps.orders.services.Product.objects.select_for_update"
        ) as mock_select:
            mock_select.return_value.filter.return_value.order_by.return_value = []

            with self.assertRaisesMessage(
                ValueError,
                "No se encontraron todos los productos del pedido.",
            ):
                cancel_order(order_id=order.pk)

        order.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(self.product.stock, 8)


class OrderViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="propietario",
            password="test-password-123",
        )

        self.other_user = User.objects.create_user(
            username="otro_cliente",
            password="test-password-123",
        )

        self.category = Category.objects.create(
            name="Categoría de pedidos",
            slug="categoria-pedidos",
        )

        self.product = Product.objects.create(
            category=self.category,
            name="Producto del pedido",
            slug="producto-del-pedido",
            price=Decimal("30.00"),
            stock=5,
        )

        self.order = create_order(
            user=self.owner,
            cart=SimpleNamespace(cart={str(self.product.pk): 1}),
        )

    def test_user_cannot_view_another_users_order_confirmation(self):
        self.client.force_login(self.other_user)

        url = reverse(
            "orders:confirmation",
            kwargs={"pk": self.order.pk},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_checkout_creates_order_and_clears_cart(self):
        self.client.force_login(self.owner)

        session = self.client.session
        session["cart"] = {str(self.product.pk): 2}
        session.save()

        response = self.client.post(reverse("orders:checkout"))

        new_order = (
            Order.objects.filter(
                user=self.owner,
            )
            .order_by("-created_at", "-pk")
            .first()
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(new_order)
        self.assertRedirects(
            response,
            reverse(
                "orders:confirmation",
                kwargs={"pk": new_order.pk},
            ),
            fetch_redirect_response=False,
        )

        new_order.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(new_order.status, Order.Status.PENDING)
        self.assertEqual(new_order.total, Decimal("60.00"))
        self.assertEqual(self.product.stock, 2)
        self.assertNotIn("cart", self.client.session)

    def test_checkout_with_insufficient_stock_preserves_cart(self):
        self.client.force_login(self.owner)

        # El producto tiene 4 unidades disponibles después
        # de crear el pedido inicial en setUp().
        session = self.client.session
        session["cart"] = {str(self.product.pk): 5}
        session.save()

        orders_before = Order.objects.filter(user=self.owner).count()

        response = self.client.post(reverse("orders:checkout"))

        self.assertRedirects(
            response,
            reverse("orders:checkout"),
            fetch_redirect_response=False,
        )

        self.assertEqual(
            Order.objects.filter(user=self.owner).count(),
            orders_before,
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

        self.assertEqual(
            self.client.session["cart"],
            {str(self.product.pk): 5},
        )

    def test_checkout_requires_login(self):
        response = self.client.get(reverse("orders:checkout"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_order_history_requires_login(self):
        response = self.client.get(reverse("orders:my_orders"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_order_history_only_shows_current_users_orders(self):
        # Creamos un pedido perteneciente a otro usuario.
        other_order = create_order(
            user=self.other_user,
            cart=SimpleNamespace(cart={str(self.product.pk): 1}),
        )

        self.client.force_login(self.owner)
        response = self.client.get(reverse("orders:my_orders"))

        self.assertEqual(response.status_code, 200)

        orders_in_response = response.context["object_list"]
        order_ids = {order.pk for order in orders_in_response}

        self.assertIn(self.order.pk, order_ids)
        self.assertNotIn(other_order.pk, order_ids)
        self.assertTrue(
            all(order.user_id == self.owner.pk for order in orders_in_response)
        )

    def test_checkout_redirects_when_cart_is_empty(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("orders:checkout"))

        self.assertRedirects(response, reverse("cart:detail"))

        messages_list = list(response.wsgi_request._messages)
        self.assertTrue(
            any(str(message) == "Tu carrito está vacío." for message in messages_list)
        )

    def test_checkout_context_contains_items_and_total(self):
        self.client.force_login(self.owner)

        session = self.client.session
        session["cart"] = {str(self.product.pk): 2}
        session.save()

        response = self.client.get(reverse("orders:checkout"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["items"]), 1)
        self.assertEqual(
            response.context["total"],
            self.product.price * 2,
        )

        item = response.context["items"][0]
        self.assertEqual(item["product"], self.product)
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(item["subtotal"], self.product.price * 2)


class OrderStatusTransitionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="usuario_estados",
            password="test-password-123",
        )
        self.category = Category.objects.create(
            name="Categoría estados",
            slug="categoria-estados",
        )
        self.product = Product.objects.create(
            category=self.category,
            name="Producto estados",
            slug="producto-estados",
            price=Decimal("30.00"),
            stock=5,
        )

        self.order = create_order(
            user=self.user,
            cart=SimpleNamespace(cart={str(self.product.pk): 1}),
        )

    def test_pending_order_can_be_paid(self):
        order = transition_order_status(
            order_id=self.order.pk,
            new_status=Order.Status.PAID,
        )

        self.assertEqual(order.status, Order.Status.PAID)

    def test_paid_order_can_be_shipped(self):
        transition_order_status(
            order_id=self.order.pk,
            new_status=Order.Status.PAID,
        )

        order = transition_order_status(
            order_id=self.order.pk,
            new_status=Order.Status.SHIPPED,
        )

        self.assertEqual(order.status, Order.Status.SHIPPED)

    def test_shipped_order_can_be_delivered(self):
        transition_order_status(
            order_id=self.order.pk,
            new_status=Order.Status.PAID,
        )
        transition_order_status(
            order_id=self.order.pk,
            new_status=Order.Status.SHIPPED,
        )

        order = transition_order_status(
            order_id=self.order.pk,
            new_status=Order.Status.DELIVERED,
        )

        self.assertEqual(order.status, Order.Status.DELIVERED)

    def test_pending_order_cannot_be_shipped_directly(self):
        with self.assertRaises(ValueError):
            transition_order_status(
                order_id=self.order.pk,
                new_status=Order.Status.SHIPPED,
            )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_delivered_order_cannot_return_to_paid(self):
        self.order.status = Order.Status.DELIVERED
        self.order.save(update_fields=["status"])

        with self.assertRaises(ValueError):
            transition_order_status(
                order_id=self.order.pk,
                new_status=Order.Status.PAID,
            )

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.DELIVERED,
        )

    def test_pending_order_can_be_cancelled_and_restores_stock(self):
        self.product.refresh_from_db()
        stock_before_cancellation = self.product.stock

        order = transition_order_status(
            order_id=self.order.pk,
            new_status=Order.Status.CANCELLED,
        )

        self.product.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(
            self.product.stock,
            stock_before_cancellation + 1,
        )

    def test_order_can_remain_in_the_same_status(self):
        original_updated_at = self.order.updated_at

        order = transition_order_status(
            order_id=self.order.pk,
            new_status=Order.Status.PENDING,
        )

        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.updated_at, original_updated_at)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

    def test_invalid_order_status_is_rejected(self):
        with self.assertRaisesMessage(
            ValueError,
            "El estado indicado no es válido.",
        ):
            transition_order_status(
                order_id=self.order.pk,
                new_status="INVALID_STATUS",
            )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

    def test_transition_nonexistent_order_raises_error(self):
        with self.assertRaisesMessage(
            ValueError,
            "El pedido no existe.",
        ):
            transition_order_status(
                order_id=999999,
                new_status=Order.Status.PAID,
            )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

    def test_non_pending_order_cannot_transition_to_cancelled(self):
        from apps.orders.services import validate_order_status_transition

        with self.assertRaisesMessage(
            ValueError,
            "Solo se pueden cancelar pedidos pendientes.",
        ):
            validate_order_status_transition(
                current_status=Order.Status.PAID,
                new_status=Order.Status.CANCELLED,
            )


class OrderAdminFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="admin_form_user",
            password="test-password-123",
        )

        self.category = Category.objects.create(
            name="Categoría admin",
            slug="categoria-admin",
        )

        self.product = Product.objects.create(
            category=self.category,
            name="Producto admin",
            slug="producto-admin",
            price=Decimal("20.00"),
            stock=5,
        )

        self.order = create_order(
            user=self.user,
            cart=SimpleNamespace(cart={str(self.product.pk): 1}),
        )

    def test_new_order_form_accepts_initial_status(self):
        form = OrderAdminForm(
            data={
                "user": self.user.pk,
                "status": Order.Status.PENDING,
                "total": "20.00",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_invalid_status_transition(self):
        self.order.status = Order.Status.DELIVERED
        self.order.save(update_fields=["status"])

        form = OrderAdminForm(
            data={
                "user": self.user.pk,
                "status": Order.Status.PAID,
                "total": str(self.order.total),
            },
            instance=self.order,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_form_rejects_cancelling_order_without_items(self):
        empty_order = Order.objects.create(
            user=self.user,
            status=Order.Status.PENDING,
            total=Decimal("0.00"),
        )

        form = OrderAdminForm(
            data={
                "user": self.user.pk,
                "status": Order.Status.CANCELLED,
                "total": "0.00",
            },
            instance=empty_order,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)
        self.assertIn(
            "No se puede cancelar un pedido sin productos.",
            form.errors["status"],
        )

    def test_form_accepts_order_that_is_already_cancelled(self):
        order = Order.objects.create(
            user=self.user,
            status=Order.Status.CANCELLED,
            total=Decimal("0.00"),
        )

        form = OrderAdminForm(
            data={
                "user": self.user.pk,
                "status": Order.Status.CANCELLED,
                "total": "0.00",
            },
            instance=order,
        )

        self.assertTrue(form.is_valid(), form.errors)


class OrderAdminConfigurationTests(TestCase):
    def test_order_admin_uses_custom_form(self):
        model_admin = OrderAdmin(Order, admin.site)

        self.assertIs(model_admin.form, OrderAdminForm)

    def test_order_admin_configuration(self):
        model_admin = OrderAdmin(Order, admin.site)

        self.assertEqual(model_admin.list_per_page, 20)
        self.assertIn("status", model_admin.list_filter)
        self.assertIn("user__username", model_admin.search_fields)
        self.assertIn("total", model_admin.readonly_fields)

    def test_order_item_inline_displays_incomplete_data(self):
        inline = OrderItemInline(Order, admin.site)

        item = SimpleNamespace(
            unit_price=None,
            quantity=1,
        )

        self.assertEqual(
            inline.subtotal_display(item),
            "Datos incompletos",
        )

    def test_order_item_inline_displays_subtotal(self):
        inline = OrderItemInline(Order, admin.site)

        item = SimpleNamespace(
            unit_price=Decimal("12.50"),
            quantity=2,
            subtotal=Decimal("25.00"),
        )

        self.assertEqual(
            inline.subtotal_display(item),
            "S/ 25.00",
        )

    def test_order_item_inline_is_readonly_and_cannot_delete(self):
        inline = OrderItemInline(Order, admin.site)

        self.assertFalse(inline.can_delete)
        self.assertEqual(
            inline.readonly_fields,
            ("product_name", "unit_price", "quantity", "subtotal_display"),
        )


class OrderAdminSaveModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="admin_save_user",
            password="test-password-123",
        )
        self.model_admin = OrderAdmin(Order, admin.site)
        self.request = SimpleNamespace()

    def test_save_model_transitions_order_status(self):
        order = Order.objects.create(
            user=self.user,
            status=Order.Status.PENDING,
            total=Decimal("0.00"),
        )

        order.status = Order.Status.PAID

        self.model_admin.save_model(
            self.request,
            order,
            form=None,
            change=True,
        )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    def test_save_model_saves_order_without_status_change(self):
        order = Order.objects.create(
            user=self.user,
            status=Order.Status.PENDING,
            total=Decimal("10.00"),
        )

        order.total = Decimal("25.00")

        self.model_admin.save_model(
            self.request,
            order,
            form=None,
            change=True,
        )

        order.refresh_from_db()
        self.assertEqual(order.total, Decimal("25.00"))
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_save_model_creates_new_order(self):
        order = Order(
            user=self.user,
            status=Order.Status.PENDING,
            total=Decimal("15.00"),
        )

        self.model_admin.save_model(
            self.request,
            order,
            form=None,
            change=False,
        )

        self.assertIsNotNone(order.pk)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())


class OrderModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="usuario_modelos",
            password="test-password-123",
        )
        self.category = Category.objects.create(
            name="Categoría modelos",
            slug="categoria-modelos",
        )
        self.product = Product.objects.create(
            category=self.category,
            name="Producto modelos",
            slug="producto-modelos",
            price=Decimal("25.00"),
            stock=5,
        )
        self.order = Order.objects.create(
            user=self.user,
            status=Order.Status.PENDING,
            total=Decimal("25.00"),
        )

    def test_order_string_representation(self):
        self.assertEqual(
            str(self.order),
            f"Pedido #{self.order.pk} - Pendiente",
        )

    def test_order_item_string_representation(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name="Producto modelos",
            unit_price=Decimal("25.00"),
            quantity=2,
        )

        self.assertEqual(
            str(item),
            "Producto modelos x 2",
        )


class OrderConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = User.objects.create_user(
            username="cliente_concurrente",
            password="test-password-123",
        )

        self.category = Category.objects.create(
            name="Categoría concurrente",
            slug="categoria-concurrente",
        )

        self.product = Product.objects.create(
            category=self.category,
            name="Última unidad",
            slug="ultima-unidad",
            price=Decimal("25.00"),
            stock=1,
        )

    def test_only_one_order_can_buy_the_last_unit(self):
        barrier = threading.Barrier(2)
        results = Queue()

        def attempt_purchase(username):
            close_old_connections()

            try:
                user = User.objects.get(username=username)
                cart = SimpleNamespace(cart={str(self.product.pk): 1})

                barrier.wait(timeout=10)

                order = create_order(user=user, cart=cart)
                results.put(("success", order.pk))

            except ValueError as error:
                results.put(("rejected", str(error)))

            except Exception as error:
                results.put(("error", repr(error)))

            finally:
                close_old_connections()

        users = [
            self.user,
            User.objects.create_user(
                username="segundo_cliente",
                password="test-password-123",
            ),
        ]

        threads = [
            threading.Thread(
                target=attempt_purchase,
                args=(user.username,),
            )
            for user in users
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(timeout=20)

        self.assertTrue(
            all(not thread.is_alive() for thread in threads),
            "Una operación de compra quedó bloqueada.",
        )

        outcomes = [results.get_nowait() for _ in threads]

        errors = [detail for status, detail in outcomes if status == "error"]
        self.assertEqual(errors, [], f"Errores inesperados: {errors}")

        successes = [detail for status, detail in outcomes if status == "success"]
        rejections = [detail for status, detail in outcomes if status == "rejected"]

        self.assertEqual(len(successes), 1, outcomes)
        self.assertEqual(len(rejections), 1, outcomes)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)

    def test_concurrent_cancellation_restores_stock_only_once(self):
        order = create_order(
            user=self.user,
            cart=SimpleNamespace(cart={str(self.product.pk): 1}),
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

        barrier = threading.Barrier(2)
        results = Queue()

        def attempt_cancellation():
            close_old_connections()

            try:
                barrier.wait(timeout=10)
                cancel_order(order_id=order.pk)
                results.put(("success", None))

            except ValueError as error:
                results.put(("rejected", str(error)))

            except Exception as error:
                results.put(("error", repr(error)))

            finally:
                close_old_connections()

        threads = [threading.Thread(target=attempt_cancellation) for _ in range(2)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(timeout=20)

        self.assertTrue(
            all(not thread.is_alive() for thread in threads),
            "Una operación de cancelación quedó bloqueada.",
        )

        outcomes = [results.get_nowait() for _ in threads]

        errors = [detail for status, detail in outcomes if status == "error"]
        self.assertEqual(errors, [], f"Errores inesperados: {errors}")

        successes = [result for result in outcomes if result[0] == "success"]
        rejections = [detail for status, detail in outcomes if status == "rejected"]

        self.assertEqual(len(successes), 1, outcomes)
        self.assertEqual(len(rejections), 1, outcomes)

        self.product.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(self.product.stock, 1)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
