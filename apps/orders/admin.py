from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import Order, OrderItem
from .services import validate_order_status_transition, transition_order_status


class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = "__all__"

    def clean_status(self):
        new_status = self.cleaned_data["status"]

        if not self.instance.pk:
            return new_status

        current_status = Order.objects.only("status").get(pk=self.instance.pk).status

        try:
            validate_order_status_transition(
                current_status=current_status,
                new_status=new_status,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        if (
            new_status == Order.Status.CANCELLED
            and current_status != Order.Status.CANCELLED
            and not OrderItem.objects.filter(order=self.instance).exists()
        ):
            raise ValidationError("No se puede cancelar un pedido sin productos.")

        return new_status


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False

    fields = (
        "product_name",
        "unit_price",
        "quantity",
        "subtotal_display",
    )

    readonly_fields = (
        "product_name",
        "unit_price",
        "quantity",
        "subtotal_display",
    )

    @admin.display(description="Subtotal")
    def subtotal_display(self, obj):
        if obj.unit_price is None or obj.quantity is None:
            return "Datos incompletos"

        return f"S/ {obj.subtotal:.2f}"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm

    list_display = (
        "id",
        "user",
        "created_at",
        "total",
        "status",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "user__username",
        "user__email",
    )

    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 20

    # El estado ya no se edita directamente desde la lista.
    # Se gestiona desde el formulario del pedido.
    readonly_fields = (
        "user",
        "total",
        "created_at",
        "updated_at",
    )

    inlines = [OrderItemInline]

    def save_model(self, request, obj, form, change):
        if change:
            current_status = Order.objects.only("status").get(pk=obj.pk).status

            if obj.status != current_status:
                transition_order_status(
                    order_id=obj.pk,
                    new_status=obj.status,
                )
                obj.refresh_from_db()
                return

        super().save_model(request, obj, form, change)
