from decimal import Decimal
from types import SimpleNamespace
from django.test import TestCase
from django.contrib.sessions.backends.db import SessionStore
from django.urls import reverse

from apps.catalog.models import Category, Product
from .services import Cart


class CartServiceTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Categoría carrito",
            slug="categoria-carrito",
        )
        self.product = Product.objects.create(
            category=self.category,
            name="Producto carrito",
            slug="producto-carrito",
            price=Decimal("25.00"),
            stock=5,
        )

        # Simulamos una petición con una sesión.
        self.request = SimpleNamespace(session=SessionStore())
        self.cart = Cart(self.request)

    def test_add_product_to_cart(self):
        self.cart.add(self.product, quantity=2)

        self.assertEqual(
            self.request.session["cart"][str(self.product.pk)],
            2,
        )

    def test_add_product_increases_existing_quantity(self):
        self.cart.add(self.product, quantity=2)
        self.cart.add(self.product, quantity=1)

        self.assertEqual(len(self.cart), 3)

    def test_override_quantity_replaces_existing_quantity(self):
        self.cart.add(self.product, quantity=2)
        self.cart.add(
            self.product,
            quantity=4,
            override_quantity=True,
        )

        self.assertEqual(len(self.cart), 4)

    def test_add_rejects_invalid_quantities(self):
        for quantity in (0, -1, 1.5, True):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValueError):
                    self.cart.add(self.product, quantity=quantity)

    def test_add_rejects_quantity_above_stock(self):
        with self.assertRaises(ValueError):
            self.cart.add(self.product, quantity=6)

        self.assertEqual(self.cart.cart, {})

    def test_add_rejects_inactive_product(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        with self.assertRaises(ValueError):
            self.cart.add(self.product)

    def test_add_rejects_product_from_inactive_category(self):
        self.category.is_active = False
        self.category.save(update_fields=["is_active"])

        with self.assertRaises(ValueError):
            self.cart.add(self.product)

    def test_remove_product_from_cart(self):
        self.cart.add(self.product, quantity=2)
        self.cart.remove(self.product.pk)

        self.assertNotIn(
            str(self.product.pk),
            self.request.session["cart"],
        )

    def test_clear_cart(self):
        self.cart.add(self.product, quantity=2)

        self.cart.clear()

        self.assertEqual(self.cart.cart, {})
        self.assertNotIn("cart", self.request.session)
        self.assertEqual(len(self.cart), 0)

    def test_cart_iteration_calculates_subtotal(self):
        self.cart.add(self.product, quantity=2)

        items = list(self.cart)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["quantity"], 2)
        self.assertEqual(
            items[0]["unit_price"],
            Decimal("25.00"),
        )
        self.assertEqual(
            items[0]["subtotal"],
            Decimal("50.00"),
        )

    def test_add_treats_invalid_existing_quantity_as_zero(self):
        self.cart.cart[str(self.product.pk)] = "cantidad-invalida"

        self.cart.add(self.product, quantity=2)

        self.assertEqual(
            self.cart.cart[str(self.product.pk)],
            2,
        )

    def test_iteration_ignores_nonexistent_product(self):
        nonexistent_product_id = "999999"
        self.cart.cart[nonexistent_product_id] = 2

        items = list(self.cart)

        self.assertEqual(items, [])

    def test_iteration_ignores_invalid_quantities(self):
        self.cart.cart = {
            str(self.product.pk): True,
            "producto-texto": "dos",
            "producto-cero": 0,
            "producto-negativo": -1,
        }

        items = list(self.cart)
        self.assertEqual(items, [])

    def test_init_resets_cart_when_session_data_is_not_a_dict(self):
        self.request.session["cart"] = ["dato", "invalido"]

        cart = Cart(self.request)

        self.assertEqual(cart.cart, {})


class CartViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Categoría vistas",
            slug="categoria-vistas",
        )
        self.product = Product.objects.create(
            category=self.category,
            name="Producto vistas",
            slug="producto-vistas",
            price=Decimal("25.00"),
            stock=5,
        )

        self.detail_url = reverse("cart:detail")
        self.add_url = reverse(
            "cart:add",
            kwargs={"product_id": self.product.pk},
        )
        self.remove_url = reverse(
            "cart:remove",
            kwargs={"product_id": self.product.pk},
        )

    def set_cart(self, items):
        session = self.client.session
        session["cart"] = items
        session.save()

    def test_cart_detail_returns_200(self):
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "cart/cart_detail.html")
        self.assertEqual(response.context["items"], [])
        self.assertEqual(response.context["total"], Decimal("0.00"))

    def test_cart_detail_displays_items_and_total(self):
        self.set_cart({str(self.product.pk): 2})

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["items"]), 1)
        self.assertEqual(response.context["total"], Decimal("50.00"))

    def test_add_view_adds_product_and_redirects(self):
        response = self.client.post(
            self.add_url,
            {"quantity": "2"},
        )

        self.assertRedirects(response, self.detail_url)

        session = self.client.session
        self.assertEqual(session["cart"][str(self.product.pk)], 2)

    def test_add_view_rejects_invalid_quantity(self):
        response = self.client.post(
            self.add_url,
            {"quantity": "abc"},
        )

        self.assertRedirects(response, self.detail_url)
        self.assertNotIn("cart", self.client.session)

    def test_add_view_returns_404_for_nonexistent_product(self):
        url = reverse("cart:add", kwargs={"product_id": 999999})

        response = self.client.post(url, {"quantity": "1"})

        self.assertEqual(response.status_code, 404)

    def test_add_view_returns_404_for_inactive_product(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        response = self.client.post(
            self.add_url,
            {"quantity": "1"},
        )

        self.assertEqual(response.status_code, 404)

    def test_add_view_rejects_get_requests(self):
        response = self.client.get(self.add_url)

        self.assertEqual(response.status_code, 405)

    def test_remove_view_removes_product_and_redirects(self):
        self.set_cart({str(self.product.pk): 2})

        response = self.client.post(self.remove_url)

        self.assertRedirects(response, self.detail_url)
        self.assertEqual(
            self.client.session["cart"],
            {},
        )

    def test_remove_view_rejects_get_requests(self):
        self.set_cart({str(self.product.pk): 2})

        response = self.client.get(self.remove_url)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            self.client.session["cart"][str(self.product.pk)],
            2,
        )

    def test_add_product_rejects_zero_quantity(self):
        response = self.client.post(
            reverse("cart:add", args=[self.product.pk]),
            {"quantity": "0"},
            follow=True,
        )

        self.assertRedirects(response, reverse("cart:detail"))
        self.assertContains(
            response,
            "La cantidad debe ser mayor que cero.",
        )
        self.assertNotIn(
            str(self.product.pk),
            self.client.session.get("cart", {}),
        )
