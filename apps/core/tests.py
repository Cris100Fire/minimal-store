from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category, Product


class HomeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Electrónica",
            slug="electronica",
        )

        cls.active_product = Product.objects.create(
            category=cls.category,
            name="Auriculares",
            slug="auriculares",
            price="49.90",
            stock=10,
        )

    def test_home_returns_200(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)

    def test_home_includes_products_in_context(self):
        response = self.client.get(reverse("core:home"))

        self.assertIn("products", response.context)
        self.assertIn(
            self.active_product,
            response.context["products"],
        )

    def test_home_excludes_inactive_products(self):
        inactive_product = Product.objects.create(
            category=self.category,
            name="Producto inactivo",
            slug="producto-inactivo",
            price="20.00",
            is_active=False,
        )

        response = self.client.get(reverse("core:home"))

        self.assertNotIn(
            inactive_product,
            response.context["products"],
        )

    def test_home_excludes_products_from_inactive_categories(self):
        inactive_category = Category.objects.create(
            name="Categoría inactiva",
            slug="categoria-inactiva",
            is_active=False,
        )

        inactive_product = Product.objects.create(
            category=inactive_category,
            name="Producto de categoría inactiva",
            slug="producto-categoria-inactiva",
            price="25.00",
        )

        response = self.client.get(reverse("core:home"))

        self.assertNotIn(
            inactive_product,
            response.context["products"],
        )

    def test_home_orders_products_by_name(self):
        Product.objects.create(
            category=self.category,
            name="Cámara",
            slug="camara",
            price="100.00",
        )

        response = self.client.get(reverse("core:home"))
        products = list(response.context["products"])

        self.assertEqual(
            [product.name for product in products],
            ["Auriculares", "Cámara"],
        )

    def test_home_displays_at_most_12_products(self):
        for number in range(12):
            Product.objects.create(
                category=self.category,
                name=f"Producto adicional {number:02}",
                slug=f"producto-adicional-{number}",
                price="10.00",
            )

        response = self.client.get(reverse("core:home"))

        self.assertEqual(len(response.context["products"]), 12)

    def test_home_uses_expected_template(self):
        response = self.client.get(reverse("core:home"))

        self.assertTemplateUsed(response, "core/home.html")
