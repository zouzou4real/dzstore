from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator


class Client(AbstractUser):
    email = models.EmailField(unique=True)
    age = models.PositiveIntegerField(
        validators=[MinValueValidator(18)],
        null=True,
        blank=False,
    )

    def __str__(self):
        return self.username


class Seller(models.Model):
    """
    Profile model for sellers that is linked to the main Client user.
    This avoids defining a second AbstractUser while still giving
    sellers their own extra fields.
    """

    user = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name="seller_profile",
    )
    business_name = models.CharField(max_length=200, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return self.user.username


class Product(models.Model):
    CATEGORY_CHOICES = [
        ("food", "Food"),
        ("cars", "Cars"),
        ("bikes", "Bikes"),
        ("phones", "Phones"),
        ("laptop", "Laptop"),
    ]

    seller = models.ForeignKey(
        Seller, on_delete=models.CASCADE, related_name="products"
    )
    publisher_name = models.CharField(max_length=200)  # business name snapshot
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.URLField(max_length=2000, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, help_text="False = soft-deleted (hidden from listings, kept for order history)")

    def __str__(self):
        return f"{self.name} ({self.publisher_name})"

class Feedback(models.Model):
    user = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="feedback_entries",
    )
    text = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.text[:50]}..."


class ContactMessage(models.Model):
    """Anonymous contact form submissions from the landing page."""
    name = models.CharField(max_length=200)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.email})"


class WishlistItem(models.Model):
    """Client's wishlist: which products they have saved."""
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="wishlist_entries",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added_at"]
        unique_together = [["client", "product"]]

    def __str__(self):
        return f"{self.client.username} — {self.product.name}"


class Order(models.Model):
    """Client order from a single seller."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    seller = models.ForeignKey(
        Seller,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} — {self.client.username} × {self.seller.user.username}"

    @property
    def total_amount(self):
        return sum(oi.subtotal for oi in self.order_items.all())


class OrderItem(models.Model):
    """Line item in an order."""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="order_items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField()
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per unit when ordered")

    class Meta:
        unique_together = [["order", "product"]]

    @property
    def subtotal(self):
        return self.quantity * self.price_at_order

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"


class Notification(models.Model):
    """Notification for a seller (e.g. new order)."""
    seller = models.ForeignKey(
        Seller,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    message = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.seller.user.username}: {self.message[:50]}..."