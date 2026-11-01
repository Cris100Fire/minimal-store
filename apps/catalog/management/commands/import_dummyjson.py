from decimal import Decimal, InvalidOperation
import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Category, Product

PRODUCTS_URL = "https://dummyjson.com/products"
CATEGORIES_URL = "https://dummyjson.com/products/categories"
INITIAL_STOCK = 10
REQUEST_TIMEOUT = 20


class Command(BaseCommand):
    help = "Importa categorías y productos desde DummyJSON."

    def handle(self, *args, **options):
        try:
            categories_data = self.fetch_categories()
            products_data = self.fetch_products()

            if not categories_data or not products_data:
                raise CommandError("DummyJSON no devolvió categorías o productos.")

            with transaction.atomic():
                categories = self.import_categories(categories_data)
                created, updated = self.import_products(products_data, categories)

        except requests.RequestException as error:
            raise CommandError(f"No se pudo conectar con DummyJSON: {error}") from error
        except (ValueError, TypeError, KeyError, InvalidOperation) as error:
            raise CommandError(
                f"Los datos recibidos no tienen el formato esperado: {error}"
            ) from error

        self.stdout.write(
            self.style.SUCCESS(
                "Importación completada correctamente.\n"
                f"Categorías procesadas: {len(categories_data)}\n"
                f"Productos nuevos: {created}\n"
                f"Productos actualizados: {updated}"
            )
        )

    def fetch_categories(self):
        response = requests.get(
            CATEGORIES_URL,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            raise ValueError("La respuesta de categorías no es una lista.")

        return data

    def fetch_products(self):
        response = requests.get(
            PRODUCTS_URL,
            params={"limit": 0},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise ValueError("La respuesta de productos no es un objeto.")

        products = data.get("products")

        if not isinstance(products, list):
            raise ValueError("No se encontró la lista de productos.")

        return products

    def import_categories(self, categories_data):
        categories = {}

        for item in categories_data:
            if not isinstance(item, dict):
                raise ValueError("Se recibió una categoría inválida.")

            name = item.get("name")
            external_slug = item.get("slug")

            if not isinstance(name, str) or not name.strip():
                raise ValueError("Una categoría no tiene nombre válido.")

            if not isinstance(external_slug, str) or not external_slug.strip():
                raise ValueError(f"La categoría {name!r} no tiene slug válido.")

            name = name.strip()
            external_slug = external_slug.strip()

            # El slug externo es la clave estable para identificar
            # la categoría durante futuras importaciones.
            category = Category.objects.filter(slug=external_slug).first()

            if category is None:
                category = Category.objects.filter(name=name).first()

            if category is None:
                category = Category.objects.create(
                    name=name,
                    slug=external_slug,
                )
                self.stdout.write(f"Categoría creada: {name}")
            else:
                # No sobrescribimos nombres o slugs que un administrador
                # pudiera haber personalizado.
                self.stdout.write(f"Categoría existente: {name}")

            categories[external_slug] = category

        return categories

    def import_products(self, products_data, categories):
        created = 0
        updated = 0

        for item in products_data:
            if not isinstance(item, dict):
                raise ValueError("Se recibió un producto inválido.")

            external_id = item.get("id")
            name = item.get("title")
            description = item.get("description", "")
            category_slug = item.get("category")
            image_url = item.get("thumbnail")
            raw_price = item.get("price")
            raw_stock = item.get("stock")

            if (
                not isinstance(external_id, int)
                or isinstance(external_id, bool)
                or external_id < 1
            ):
                raise ValueError("Un producto tiene un ID inválido.")

            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"El producto {external_id} no tiene título válido.")

            if not isinstance(category_slug, str):
                raise ValueError(
                    f"El producto {external_id} no tiene categoría válida."
                )

            category = categories.get(category_slug)

            if category is None:
                raise ValueError(
                    f"No se encontró la categoría {category_slug!r} "
                    f"del producto {external_id}."
                )

            try:
                price = Decimal(str(raw_price))
            except (InvalidOperation, ValueError, TypeError) as error:
                raise ValueError(
                    f"Precio inválido en el producto {external_id}."
                ) from error

            if not price.is_finite() or price < 0:
                raise ValueError(
                    f"Precio fuera de rango válido en el producto {external_id}."
                )

            if price != price.quantize(Decimal("0.01")):
                raise ValueError(
                    f"El producto {external_id} tiene más de dos "
                    "decimales en su precio."
                )

            if price >= Decimal("100000000"):
                raise ValueError(
                    f"El precio del producto {external_id} "
                    "supera la capacidad del modelo."
                )

            if (
                not isinstance(raw_stock, int)
                or isinstance(raw_stock, bool)
                or raw_stock < 0
            ):
                raise ValueError(f"Stock inválido en el producto {external_id}.")

            if len(name.strip()) > 200:
                raise ValueError(
                    f"El nombre del producto {external_id} es demasiado largo."
                )

            if image_url is not None and not isinstance(image_url, str):
                raise ValueError(f"Imagen inválida en el producto {external_id}.")

            image_url = image_url or None

            if image_url and len(image_url) > 5000:
                raise ValueError(
                    f"La URL de imagen del producto {external_id} "
                    "es demasiado larga."
                )

            description = description or ""

            if not isinstance(description, str):
                raise ValueError(f"Descripción inválida en el producto {external_id}.")

            product = Product.objects.filter(external_id=external_id).first()

            if product is None:
                # Un slug puede colisionar con uno personalizado.
                base_slug = slugify(name) or f"product-{external_id}"
                product_slug = base_slug
                suffix = 2

                while Product.objects.filter(slug=product_slug).exists():
                    product_slug = f"{base_slug}-{suffix}"
                    suffix += 1

                Product.objects.create(
                    external_id=external_id,
                    category=category,
                    name=name.strip(),
                    slug=product_slug,
                    description=description,
                    price=price,
                    stock=raw_stock,
                    image_url=image_url,
                )

                created += 1
                continue

            # En productos existentes actualizamos los datos descriptivos,
            # pero conservamos el stock gestionado por nuestra tienda.
            product.category = category
            product.name = name.strip()
            product.description = description
            product.price = price
            product.image_url = image_url
            product.save(
                update_fields=[
                    "category",
                    "name",
                    "description",
                    "price",
                    "image_url",
                    "updated_at",
                ]
            )

            updated += 1

        return created, updated
