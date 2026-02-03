from django.contrib import admin
from .models import Client, Seller, Product, WishlistItem, Order, OrderItem, Notification, ContactMessage


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price_at_order")


class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "seller", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("client__username", "seller__user__username")
    inlines = [OrderItemInline]


admin.site.register(Order, OrderAdmin)


class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "seller", "order", "message", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("message", "seller__user__username")
    ordering = ("-created_at",)


admin.site.register(Notification, NotificationAdmin)


class ClientAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "age", "is_staff")


class SellerAdmin(admin.ModelAdmin):
    list_display = ("user", "business_name", "phone_number")


admin.site.register(Client, ClientAdmin)
admin.site.register(Seller, SellerAdmin)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "publisher_name", "category", "quantity", "price", "created_at")
    list_filter = ("category",)
    search_fields = ("name", "publisher_name")


admin.site.register(Product, ProductAdmin)


class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("client", "product", "added_at")
    list_filter = ("added_at",)
    search_fields = ("client__username", "product__name")


admin.site.register(WishlistItem, WishlistItemAdmin)


class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "created_at")
    search_fields = ("name", "email", "message")
    readonly_fields = ("name", "email", "message", "created_at")
    ordering = ("-created_at",)


admin.site.register(ContactMessage, ContactMessageAdmin)