from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from .models import Category, Product


class ProductListView(ListView):
    model = Product
    template_name = "catalog/product_list.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        queryset = Product.objects.filter(
            is_active=True,
            category__is_active=True,
        ).select_related("category")

        category_slug = self.kwargs.get("category_slug")
        self.selected_category = None

        if category_slug:
            self.selected_category = get_object_or_404(
                Category,
                slug=category_slug,
                is_active=True,
            )
            queryset = queryset.filter(category=self.selected_category)

        return queryset.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(is_active=True)
        context["selected_category"] = getattr(self, "selected_category", None)
        return context


class ProductDetailView(DetailView):
    model = Product
    template_name = "catalog/product_detail.html"
    context_object_name = "product"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Product.objects.filter(
            is_active=True,
            category__is_active=True,
        ).select_related("category")
