from django.test import TestCase
from django.urls import reverse

from .models import Category, Product


class ProductListViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Electrónica",
            slug="electronica",
        )

        cls.other_category = Category.objects.create(
            name="Accesorios",
            slug="accesorios",
        )

        cls.product = Product.objects.create(
            category=cls.category,
            name="Auriculares",
            slug="auriculares",
            price="49.90",
            stock=10,
        )

    def test_product_list_returns_200(self):
        response = self.client.get(reverse("catalog:product_list"))

        self.assertEqual(response.status_code, 200)

    def test_list_displays_active_products(self):
        response = self.client.get(reverse("catalog:product_list"))

        self.assertContains(response, "Auriculares")
        self.assertIn(self.product, response.context["products"])

    def test_list_excludes_inactive_products(self):
        inactive_product = Product.objects.create(
            category=self.category,
            name="Producto inactivo",
            slug="producto-inactivo",
            price="20.00",
            is_active=False,
        )

        response = self.client.get(reverse("catalog:product_list"))

        self.assertNotIn(inactive_product, response.context["products"])

    def test_list_excludes_products_from_inactive_categories(self):
        inactive_category = Category.objects.create(
            name="Categoría inactiva",
            slug="categoria-inactiva",
            is_active=False,
        )

        inactive_category_product = Product.objects.create(
            category=inactive_category,
            name="Producto de categoría inactiva",
            slug="producto-categoria-inactiva",
            price="25.00",
        )

        response = self.client.get(reverse("catalog:product_list"))

        self.assertNotIn(
            inactive_category_product,
            response.context["products"],
        )

    def test_list_orders_products_by_name(self):
        Product.objects.create(
            category=self.category,
            name="Cámara",
            slug="camara",
            price="100.00",
        )

        response = self.client.get(reverse("catalog:product_list"))
        products = list(response.context["products"])

        self.assertEqual(
            [product.name for product in products],
            ["Auriculares", "Cámara"],
        )

    def test_category_filter_displays_only_selected_category(self):
        other_product = Product.objects.create(
            category=self.other_category,
            name="Cable USB",
            slug="cable-usb",
            price="9.90",
        )

        response = self.client.get(
            reverse(
                "catalog:category_products",
                kwargs={"category_slug": self.category.slug},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Auriculares")
        self.assertNotIn(other_product, response.context["products"])
        self.assertEqual(
            response.context["selected_category"].slug,
            self.category.slug,
        )

    def test_nonexistent_category_returns_404(self):
        response = self.client.get(
            reverse(
                "catalog:category_products",
                kwargs={"category_slug": "no-existe"},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_product_list_paginates_after_12_products(self):
        for number in range(12):
            Product.objects.create(
                category=self.category,
                name=f"Producto adicional {number:02}",
                slug=f"producto-adicional-{number}",
                price="10.00",
            )

        response = self.client.get(reverse("catalog:product_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["products"]), 12)
        self.assertTrue(response.context["is_paginated"])

    def test_inactive_category_returns_404_when_filtered(self):
        inactive_category = Category.objects.create(
            name="Categoría oculta",
            slug="categoria-oculta",
            is_active=False,
        )

        response = self.client.get(
            reverse(
                "catalog:category_products",
                kwargs={"category_slug": inactive_category.slug},
            )
        )

        self.assertEqual(response.status_code, 404)


class ProductDetailViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Electrónica",
            slug="electronica",
        )

        cls.product = Product.objects.create(
            category=cls.category,
            name="Auriculares",
            slug="auriculares",
            price="49.90",
            stock=10,
        )

    def test_active_product_detail_returns_200(self):
        response = self.client.get(
            reverse(
                "catalog:product_detail",
                kwargs={"slug": self.product.slug},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["product"], self.product)

    def test_inactive_product_detail_returns_404(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        response = self.client.get(
            reverse(
                "catalog:product_detail",
                kwargs={"slug": self.product.slug},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_product_from_inactive_category_returns_404(self):
        self.category.is_active = False
        self.category.save(update_fields=["is_active"])

        response = self.client.get(
            reverse(
                "catalog:product_detail",
                kwargs={"slug": self.product.slug},
            )
        )

        self.assertEqual(response.status_code, 404)


class CatalogModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Categoría de prueba",
            slug="categoria-prueba",
        )
        cls.product = Product.objects.create(
            category=cls.category,
            name="Producto de prueba",
            slug="producto-prueba",
            price="25.00",
            stock=5,
        )

    def test_category_string_representation(self):
        self.assertEqual(str(self.category), "Categoría de prueba")

    def test_product_string_representation(self):
        self.assertEqual(str(self.product), "Producto de prueba")

    def test_product_is_available_when_active_with_stock(self):
        self.assertTrue(self.product.is_available)

    def test_product_is_unavailable_when_inactive(self):
        self.product.is_active = False

        self.assertFalse(self.product.is_available)

    def test_product_is_unavailable_when_category_is_inactive(self):
        self.category.is_active = False

        self.assertFalse(self.product.is_available)

    def test_product_is_unavailable_when_stock_is_zero(self):
        self.product.stock = 0

        self.assertFalse(self.product.is_available)
