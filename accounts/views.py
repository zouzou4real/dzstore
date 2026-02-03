from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.views import PasswordChangeView as AuthPasswordChangeView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from decimal import Decimal, InvalidOperation
from django.db.models import Count, Sum, F, Q
from django.db.models.fields import DecimalField
from django.db.models.expressions import ExpressionWrapper
from django.http import HttpResponse
from .forms import (
    ClientRegistrationForm,
    ClientUpdateForm,
    SellerRegistrationForm,
    SellerUpdateForm,
    FeedbackForm,
    LandingContactForm,
    CustomPasswordChangeForm,
    ProductForm,
    FakePaymentForm,
)
from .models import Client, Seller, Feedback, Product, WishlistItem, Order, OrderItem, Notification


def _is_seller(user):
    """Safe check: avoid hasattr(user, 'seller_profile') which raises if no seller."""
    if user is None or not user.is_authenticated:
        return False
    return Seller.objects.filter(user=user).exists()


def home(request):
    return HttpResponse("Hello! Django is working 🚀")


# Client views
def register_view(request):
    if request.method == "POST":
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home_client")
    else:
        form = ClientRegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


@ensure_csrf_cookie
def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        try:
            # Only allow pure client accounts (no seller profile attached)
            user_obj = Client.objects.get(email=email, seller_profile__isnull=True)
            user = authenticate(request, username=user_obj.username, password=password)
            if user is not None:
                login(request, user)
                return redirect("home_client")
            else:
                messages.error(request, "Invalid email or password.")
        except Client.DoesNotExist:
            messages.error(request, "Client account does not exist. If you are a seller, use the seller login page.")
    return render(request, "accounts/login.html")


def landing_view(request):
    """Public landing page — no authentication required. Handles contact form POST."""
    form = LandingContactForm()
    if request.method == "POST":
        form = LandingContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you for your message. We will get back to you soon.")
            return redirect(reverse("landing") + "#contact")
    return render(request, "accounts/landing.html", {"landing_contact_form": form})


@login_required
def home_client_view(request):
    if _is_seller(request.user):
        messages.error(request, "This area is for clients only. You are logged in as a seller.")
        return redirect("home_seller")
    # Base queryset: only active and available products for the marketplace.
    products_qs = (
        Product.objects.filter(is_active=True, quantity__gt=0)
        .select_related("seller", "seller__user")
    )

    # Read raw GET parameters so we can both filter and echo them back in the form.
    search_query = request.GET.get("q", "").strip()
    seller_param = request.GET.get("seller", "").strip()
    min_price_raw = request.GET.get("min_price", "").strip()
    max_price_raw = request.GET.get("max_price", "").strip()
    category_param = request.GET.get("category", "").strip()

    # Text search across name and description (case-insensitive).
    if search_query:
        products_qs = products_qs.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Filter by seller (if a valid integer ID was provided).
    selected_seller_id = None
    if seller_param:
        try:
            selected_seller_id = int(seller_param)
        except (TypeError, ValueError):
            selected_seller_id = None
        if selected_seller_id:
            products_qs = products_qs.filter(seller_id=selected_seller_id)

    # Helper: safely convert a string to Decimal, returning None on invalid input.
    def _to_decimal(value):
        try:
            return Decimal(value)
        except (InvalidOperation, TypeError, ValueError):
            return None

    # Filter by price range if provided.
    min_price = _to_decimal(min_price_raw) if min_price_raw else None
    max_price = _to_decimal(max_price_raw) if max_price_raw else None
    if min_price is not None:
        products_qs = products_qs.filter(price__gte=min_price)
    if max_price is not None:
        products_qs = products_qs.filter(price__lte=max_price)

    # Filter by category slug using Product.CATEGORY_CHOICES.
    # We don't rely on a dedicated Category model, so if choices disappear later,
    # the dropdown will simply hide (graceful degradation).
    valid_categories = getattr(Product, "CATEGORY_CHOICES", []) or []
    valid_category_slugs = {slug for slug, _ in valid_categories}
    category_slug = None
    if category_param and category_param in valid_category_slugs:
        category_slug = category_param
        products_qs = products_qs.filter(category=category_slug)

    # Data for dropdowns and listings.
    sellers = Seller.objects.all().order_by("user__username")
    products = products_qs.order_by("-created_at")

    context = {
        "sellers": sellers,
        "products": products,
        "categories": valid_categories,
        "search_query": search_query,
        "selected_seller_id": selected_seller_id,
        "min_price": min_price_raw,
        "max_price": max_price_raw,
        "selected_category": category_slug or "",
    }
    return render(request, "accounts/homeclient.html", context)


@login_required
def profile_view(request):
    if _is_seller(request.user):
        messages.error(request, "This profile page is for clients only.")
        return redirect("seller_profile")
    return render(request, "accounts/profileclient.html")


@login_required
def client_update_profile_view(request):
    if _is_seller(request.user):
        messages.error(request, "This page is for clients only.")
        return redirect("seller_profile")
    if request.method == "POST":
        form = ClientUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("profile_client")
    else:
        form = ClientUpdateForm(instance=request.user)
    return render(request, "accounts/profileclient_update.html", {"form": form})


def logout_view(request):
    logout(request)  # This destroys the session
    messages.info(request, "You have been logged out.")  # Optional: let them know it worked
    return redirect("login")  # Redirect back to the login page


def _password_change_realm(request):
    """Return (base_template, back_url_name, back_label) for the current user/URL realm."""
    path = request.path
    if "superadmin" in path:
        return "accounts/base_superadmin.html", "superadmin_profile", "Back to profile"
    if "seller" in path:
        return "accounts/base_seller.html", "seller_profile", "Back to profile"
    return "accounts/base_client.html", "profile_client", "Back to profile"


@method_decorator(login_required, name="dispatch")
class PasswordChangeView(AuthPasswordChangeView):
    """Reusable password change: old password + new password with site rules. Success URL by realm."""
    form_class = CustomPasswordChangeForm
    template_name = "accounts/password_change.html"

    def get_success_url(self):
        _, back_url_name, _ = _password_change_realm(self.request)
        return reverse(back_url_name)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_template, back_url_name, back_label = _password_change_realm(self.request)
        context["base_template"] = base_template
        context["back_url"] = reverse(back_url_name)
        context["back_label"] = back_label
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Your password has been changed successfully.")
        return response


# Seller views
def seller_register_view(request):
    if request.method == "POST":
        form = SellerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home_seller")
    else:
        form = SellerRegistrationForm()
    return render(request, "accounts/seller_register.html", {"form": form})


@ensure_csrf_cookie
def seller_login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        try:
            # Only allow users that have a seller profile
            user_obj = Client.objects.get(email=email, seller_profile__isnull=False)
            user = authenticate(request, username=user_obj.username, password=password)
            if user is not None and _is_seller(user):
                login(request, user)
                return redirect("home_seller")
            messages.error(request, "Invalid email or password.")
        except Client.DoesNotExist:
            messages.error(request, "Seller account does not exist. If you are a client, use the client login page.")
    return render(request, "accounts/seller_login.html")


@login_required
def home_seller_view(request):
    if not _is_seller(request.user):
        messages.error(request, "Access denied. Seller account required.")
        return redirect("seller_login")
    seller = request.user.seller_profile
    products_count = seller.products.filter(is_active=True).count()
    orders_count = seller.orders.count()
    pending_orders_count = seller.orders.filter(status="pending").count()
    completed_orders_count = seller.orders.filter(status="completed").count()
    total_sales = (
        OrderItem.objects.filter(order__seller=seller, order__status="completed").aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") * F("price_at_order"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
        )["total"]
        or 0
    )
    return render(
        request,
        "accounts/homeseller.html",
        {
            "products_count": products_count,
            "orders_count": orders_count,
            "pending_orders_count": pending_orders_count,
            "completed_orders_count": completed_orders_count,
            "total_sales": total_sales,
        },
    )


@login_required
def seller_profile_view(request):
    if not _is_seller(request.user):
        messages.error(request, "Access denied. Seller account required.")
        return redirect("seller_login")
    return render(request, "accounts/profileseller.html")


@login_required
def seller_update_profile_view(request):
    if not _is_seller(request.user):
        messages.error(request, "Access denied. Seller account required.")
        return redirect("seller_login")
    seller_profile = Seller.objects.get(user=request.user)
    if request.method == "POST":
        form = SellerUpdateForm(
            request.POST,
            instance=request.user,
            seller_profile=seller_profile,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Seller profile updated successfully.")
            return redirect("seller_profile")
    else:
        form = SellerUpdateForm(instance=request.user, seller_profile=seller_profile)
    return render(request, "accounts/profileseller_update.html", {"form": form})


def seller_logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("seller_login")


@login_required
def feedback_view(request):
    qs = Feedback.objects.select_related("user").all()
    feedback_list = []
    for fb in qs:
        is_seller = _is_seller(fb.user)
        display_name = fb.user.username
        if is_seller:
            sp = Seller.objects.get(user=fb.user)
            display_name = sp.business_name or fb.user.username
        feedback_list.append({
            "fb": fb,
            "is_seller": is_seller,
            "display_name": display_name,
            "is_own": fb.user_id == request.user.pk,
        })
    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            messages.success(request, "Feedback submitted. Thank you!")
            return redirect("feedback")
    else:
        form = FeedbackForm()
    is_seller = _is_seller(request.user)
    return render(
        request,
        "accounts/feedback.html",
        {
            "form": form,
            "feedback_list": feedback_list,
            "is_seller": is_seller,
            "base_template": "accounts/base_seller.html" if is_seller else "accounts/base_client.html",
        },
    )


@login_required
def feedback_delete_view(request, feedback_id):
    """Client or seller can delete only their own feedback (POST only)."""
    if request.method != "POST":
        return redirect("feedback")
    try:
        fb = Feedback.objects.get(pk=feedback_id, user=request.user)
    except Feedback.DoesNotExist:
        messages.error(request, "Feedback not found or you cannot delete it.")
        return redirect("feedback")
    fb.delete()
    messages.success(request, "Your feedback was deleted.")
    return redirect("feedback")


@login_required
def seller_products_view(request):
    if not _is_seller(request.user):
        messages.error(request, "Access denied. Seller account required.")
        return redirect("seller_login")
    seller = Seller.objects.get(user=request.user)
    products = Product.objects.filter(seller=seller, is_active=True).order_by("-created_at")
    return render(request, "accounts/seller_products.html", {"products": products})


@login_required
def seller_product_add_view(request):
    if not _is_seller(request.user):
        messages.error(request, "Access denied. Seller account required.")
        return redirect("seller_login")
    seller = Seller.objects.get(user=request.user)
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = seller
            product.publisher_name = seller.business_name or request.user.username
            product.save()
            messages.success(request, "Product added successfully.")
            return redirect("seller_products")
        else:
            # surface form errors so seller knows why save failed
            for field, errs in form.errors.items():
                for e in errs:
                    messages.error(request, f"{field}: {e}")
    else:
        form = ProductForm()
    return render(request, "accounts/seller_product_add.html", {"form": form})


@login_required
def seller_product_edit_view(request, product_id):
    """Seller edits one of their products (quantity, description, etc.)."""
    if not _is_seller(request.user):
        messages.error(request, "Access denied. Seller account required.")
        return redirect("seller_login")
    seller = Seller.objects.get(user=request.user)
    try:
        product = Product.objects.get(pk=product_id, seller=seller, is_active=True)
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect("seller_products")
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully.")
            return redirect("seller_products")
        else:
            for field, errs in form.errors.items():
                for e in errs:
                    messages.error(request, f"{field}: {e}")
    else:
        form = ProductForm(instance=product)
    return render(request, "accounts/seller_product_edit.html", {"form": form, "product": product})


@login_required
def seller_product_delete_view(request, product_id):
    """Seller deletes one of their products. POST only, with confirmation on the client."""
    if not _is_seller(request.user):
        messages.error(request, "Access denied. Seller account required.")
        return redirect("seller_login")
    if request.method != "POST":
        return redirect("seller_product_edit", product_id=product_id)
    seller = Seller.objects.get(user=request.user)
    try:
        product = Product.objects.get(pk=product_id, seller=seller)
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect("seller_products")
    product_name = product.name
    product.is_active = False
    product.save(update_fields=["is_active"])
    messages.success(request, f"Product “{product_name}” has been deleted.")
    return redirect("seller_products")


@login_required
def seller_notifications_view(request):
    """List notifications for the current seller. Optionally mark all as completed."""
    if not _is_seller(request.user):
        messages.error(request, "Access denied. Seller account required.")
        return redirect("seller_login")
    seller = Seller.objects.get(user=request.user)
    notifications = Notification.objects.filter(seller=seller).select_related("order", "order__client").order_by("-created_at")
    if request.method == "POST" and request.POST.get("mark_completed") == "all":
        unread = notifications.filter(is_read=False)
        for n in unread:
            if n.order_id and n.order.seller_id == seller.pk and n.order.status == "pending":
                n.order.status = "completed"
                n.order.save(update_fields=["status"])
        unread.update(is_read=True)
        messages.success(request, "All pending orders marked as completed.")
        return redirect("seller_notifications")
    return render(
        request,
        "accounts/seller_notifications.html",
        {"notifications": notifications, "unread_count": notifications.filter(is_read=False).count()},
    )


@login_required
def seller_notification_mark_read_view(request, notification_id):
    """Mark a single notification as completed: set related order to completed (if pending), then mark read (POST)."""
    if request.method != "POST":
        return redirect("seller_notifications")
    if not _is_seller(request.user):
        return redirect("seller_login")
    seller = Seller.objects.get(user=request.user)
    try:
        notification = Notification.objects.select_related("order").get(pk=notification_id, seller=seller)
    except Notification.DoesNotExist:
        messages.error(request, "Notification not found or access denied.")
        return redirect("seller_notifications")
    if notification.order_id and notification.order.status == "pending":
        notification.order.status = "completed"
        notification.order.save(update_fields=["status"])
    Notification.objects.filter(pk=notification_id, seller=seller).update(is_read=True)
    messages.success(request, "Order marked as completed.")
    return redirect("seller_notifications")


# ===== CLIENT: CART HELPERS =====

_CART_SELLER_KEY = "cart_seller_id"
_CART_ITEMS_KEY = "cart_items"


def _get_cart(request):
    """Return (seller_id or None, {product_id: qty})."""
    sid = request.session.get(_CART_SELLER_KEY)
    items = request.session.get(_CART_ITEMS_KEY) or {}
    return sid, {int(k): int(v) for k, v in items.items() if v > 0}


def _set_cart(request, seller_id, items):
    """items: dict product_id -> qty."""
    request.session[_CART_SELLER_KEY] = seller_id
    request.session[_CART_ITEMS_KEY] = {str(k): v for k, v in items.items() if v > 0}
    request.session.modified = True


def _clear_cart(request):
    request.session.pop(_CART_SELLER_KEY, None)
    request.session.pop(_CART_ITEMS_KEY, None)
    request.session.modified = True


def _build_cart_context(request):
    """Build {seller, cart_lines, total} from session, or None if empty. Updates session with capped qtys."""
    cart_sid, items = _get_cart(request)
    if not cart_sid or not items:
        return None
    try:
        seller = Seller.objects.get(pk=cart_sid)
    except Seller.DoesNotExist:
        _clear_cart(request)
        return None
    product_ids = list(items.keys())
    products = Product.objects.filter(pk__in=product_ids, seller=seller, is_active=True).in_bulk()
    cart_lines = []
    updated = {}
    for pid, qty in items.items():
        if pid not in products:
            continue
        p = products[pid]
        available = p.quantity
        qty = min(qty, available) if available else 0
        if qty <= 0:
            continue
        updated[pid] = qty
        cart_lines.append({"product": p, "quantity": qty, "subtotal": qty * p.price})
    if not cart_lines:
        _clear_cart(request)
        return None
    _set_cart(request, cart_sid, updated)
    total = sum(cl["subtotal"] for cl in cart_lines)
    return {"seller": seller, "cart_lines": cart_lines, "total": total}


# ===== CLIENT: SELLER MARKET, CART, WISHLIST =====


@login_required
def client_seller_products_view(request, seller_id):
    """Client views a seller's market (products by category, full details). Add to cart, wishlist, or order."""
    if _is_seller(request.user):
        messages.error(request, "This area is for clients only.")
        return redirect("home_seller")
    try:
        seller = Seller.objects.get(pk=seller_id)
    except Seller.DoesNotExist:
        messages.error(request, "Seller not found.")
        return redirect("home_client")
    products_qs = Product.objects.filter(seller=seller, is_active=True).order_by("name")
    wishlist_product_ids = set(
        WishlistItem.objects.filter(client=request.user).values_list("product_id", flat=True)
    )
    cart_seller_id, cart_items = _get_cart(request)
    cart_count = sum(cart_items.values()) if cart_seller_id == seller_id else 0
    # Group products by category (order follows Product.CATEGORY_CHOICES)
    categories = []
    for slug, label in Product.CATEGORY_CHOICES:
        products_in_cat = list(products_qs.filter(category=slug))
        if products_in_cat:
            categories.append({"name": label, "slug": slug, "products": products_in_cat})
    return render(
        request,
        "accounts/client_seller_products.html",
        {
            "seller": seller,
            "categories": categories,
            "wishlist_product_ids": wishlist_product_ids,
            "cart_count": cart_count,
        },
    )


@login_required
def add_to_cart_view(request, seller_id):
    """Add a product to the client's cart (POST: product_id, quantity). Cart is per-seller."""
    if _is_seller(request.user):
        messages.error(request, "Cart is for clients only.")
        return redirect("home_seller")
    if request.method != "POST":
        return redirect("client_seller_products", seller_id=seller_id)
    try:
        seller = Seller.objects.get(pk=seller_id)
    except Seller.DoesNotExist:
        messages.error(request, "Seller not found.")
        return redirect("home_client")
    try:
        product_id = int(request.POST.get("product_id"))
        qty = max(1, int(request.POST.get("quantity", 1)))
    except (TypeError, ValueError):
        messages.error(request, "Invalid quantity.")
        return redirect("client_seller_products", seller_id=seller_id)
    try:
        product = Product.objects.get(pk=product_id, seller=seller, is_active=True)
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect("client_seller_products", seller_id=seller_id)
    if product.quantity < 1:
        messages.error(request, f"« {product.name} » is out of stock.")
        return redirect("client_seller_products", seller_id=seller_id)
    cart_sid, items = _get_cart(request)
    if cart_sid is not None and cart_sid != seller_id:
        items = {}
    items[product_id] = items.get(product_id, 0) + qty
    items[product_id] = min(items[product_id], product.quantity)
    _set_cart(request, seller_id, items)
    messages.success(request, f"Added « {product.name} » to cart.")
    next_url = request.POST.get("next", "").strip() or request.GET.get("next", "").strip()
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("client_seller_products", seller_id=seller_id)


@login_required
def cart_view(request):
    """View cart (current seller from session). Clients only."""
    if _is_seller(request.user):
        messages.error(request, "Cart is for clients only.")
        return redirect("home_seller")
    ctx = _build_cart_context(request)
    if ctx is None:
        messages.info(request, "Your cart is empty.")
        return redirect("home_client")
    return render(request, "accounts/cart.html", ctx)


@login_required
def cart_remove_view(request, product_id):
    """Remove a product from cart (POST)."""
    if _is_seller(request.user):
        return redirect("home_seller")
    if request.method != "POST":
        return redirect("cart")
    cart_sid, items = _get_cart(request)
    if not cart_sid or not items:
        return redirect("home_client")
    product_id = int(product_id)
    items.pop(product_id, None)
    if not items:
        _clear_cart(request)
        return redirect("home_client")
    _set_cart(request, cart_sid, items)
    return redirect("cart")


@login_required
def checkout_view(request):
    """Fake payment page (GET) or process payment + create order (POST). Clients only."""
    if _is_seller(request.user):
        messages.error(request, "Orders are for clients only.")
        return redirect("home_seller")
    ctx = _build_cart_context(request)
    if ctx is None:
        messages.error(request, "Cart is empty.")
        return redirect("home_client")
    seller = ctx["seller"]
    cart_lines = ctx["cart_lines"]
    total = ctx["total"]

    if request.method == "GET":
        form = FakePaymentForm()
        ctx["form"] = form
        return render(request, "accounts/checkout_payment.html", ctx)

    form = FakePaymentForm(request.POST)
    if not form.is_valid():
        ctx["form"] = form
        return render(request, "accounts/checkout_payment.html", ctx)

    cart_sid, items = _get_cart(request)
    if not cart_sid or cart_sid != seller.pk:
        messages.error(request, "Cart changed. Please try again.")
        return redirect("cart")
    product_ids = list(items.keys())
    products = Product.objects.filter(pk__in=product_ids, seller=seller, is_active=True).in_bulk()
    order_lines = []
    for pid, qty in items.items():
        if pid not in products:
            continue
        p = products[pid]
        qty = min(qty, p.quantity)
        if qty <= 0:
            continue
        order_lines.append((p, qty))
    if not order_lines:
        _clear_cart(request)
        messages.error(request, "No valid items to order.")
        return redirect("home_client")
    order = Order.objects.create(client=request.user, seller=seller, status="pending")
    for p, qty in order_lines:
        OrderItem.objects.create(order=order, product=p, quantity=qty, price_at_order=p.price)
        Product.objects.filter(pk=p.pk).update(quantity=p.quantity - qty)
    Notification.objects.create(
        seller=seller,
        order=order,
        message=f"New order #{order.pk} from {request.user.username} — {order.total_amount} DZD",
        is_read=False,
    )
    _clear_cart(request)
    method = form.cleaned_data.get("method", "card")
    method_label = "DZD Pay" if method == "dzd_pay" else "Card"
    messages.success(
        request,
        f"Payment successful ({method_label}). Order #{order.pk} placed. Total: {order.total_amount} DZD.",
    )
    return redirect("client_seller_products", seller_id=seller.pk)


@login_required
def add_to_wishlist_view(request, product_id):
    """Add a product to the client's wishlist."""
    if _is_seller(request.user):
        messages.error(request, "Wishlist is for clients only.")
        return redirect("home_seller")
    try:
        product = Product.objects.get(pk=product_id, is_active=True)
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect("home_client")
    _, created = WishlistItem.objects.get_or_create(client=request.user, product=product)
    if created:
        messages.success(request, f"Added « {product.name} » to your wishlist.")
    else:
        messages.info(request, "Already in your wishlist.")
    next_url = request.GET.get("next", "").strip()
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("client_seller_products", seller_id=product.seller_id)


@login_required
def remove_from_wishlist_view(request, product_id):
    """Remove a product from the client's wishlist (POST only)."""
    if request.method != "POST":
        return redirect("wishlist")
    if _is_seller(request.user):
        messages.error(request, "Wishlist is for clients only.")
        return redirect("home_seller")
    deleted = WishlistItem.objects.filter(client=request.user, product_id=product_id).delete()
    if deleted[0]:
        messages.success(request, "Removed from wishlist.")
    return redirect("wishlist")


@login_required
def wishlist_view(request):
    """Client sees their wishlist and can remove items."""
    if _is_seller(request.user):
        messages.error(request, "Wishlist is for clients only.")
        return redirect("home_seller")
    items = WishlistItem.objects.filter(client=request.user).select_related("product", "product__seller")
    return render(request, "accounts/wishlist.html", {"wishlist_items": items})


# ===== SUPER ADMIN VIEWS =====


@ensure_csrf_cookie
def superadmin_login_view(request):
    """Superadmin login (username + password). Only users with is_superuser=True can log in."""
    if request.user.is_authenticated and getattr(request.user, "is_superuser", False):
        return redirect("superadmin_home")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None and getattr(user, "is_superuser", False):
            login(request, user)
            return redirect("superadmin_home")
        messages.error(request, "Invalid credentials or not a superadmin account.")
    return render(request, "accounts/superadmin_login.html")


@login_required
def superadmin_home_view(request):
    """Superadmin dashboard: clients count, sellers count, products per seller, feedback count."""
    if not getattr(request.user, "is_superuser", False):
        messages.error(request, "Access denied. Superadmin only.")
        return redirect("superadmin_login")
    clients_count = Client.objects.filter(seller_profile__isnull=True).count()
    sellers_count = Seller.objects.count()
    sellers_with_products = Seller.objects.annotate(product_count=Count("products")).order_by("-product_count")
    feedback_count = Feedback.objects.count()
    return render(
        request,
        "accounts/superadmin_home.html",
        {
            "clients_count": clients_count,
            "sellers_count": sellers_count,
            "sellers_with_products": sellers_with_products,
            "feedback_count": feedback_count,
        },
    )


@login_required
def superadmin_profile_view(request):
    """Superadmin profile: username, email, password (masked)."""
    if not getattr(request.user, "is_superuser", False):
        messages.error(request, "Access denied. Superadmin only.")
        return redirect("superadmin_login")
    return render(request, "accounts/superadmin_profile.html")


@login_required
def superadmin_feedback_view(request):
    """List all feedback; superadmin can delete any."""
    if not getattr(request.user, "is_superuser", False):
        messages.error(request, "Access denied. Superadmin only.")
        return redirect("superadmin_login")
    feedback_list = Feedback.objects.select_related("user").order_by("-created_at")
    return render(request, "accounts/superadmin_feedback.html", {"feedback_list": feedback_list})


@login_required
def superadmin_transactions_view(request):
    """Archive of all orders (transactions) for superadmin."""
    if not getattr(request.user, "is_superuser", False):
        messages.error(request, "Access denied. Superadmin only.")
        return redirect("superadmin_login")
    orders = (
        Order.objects.select_related("client", "seller", "seller__user")
        .prefetch_related("order_items", "order_items__product")
        .order_by("-created_at")
    )
    return render(request, "accounts/superadmin_transactions.html", {"orders": orders})


@login_required
def superadmin_feedback_delete_view(request, feedback_id):
    """Delete a feedback entry (POST only)."""
    if request.method != "POST":
        return redirect("superadmin_feedback")
    if not getattr(request.user, "is_superuser", False):
        messages.error(request, "Access denied. Superadmin only.")
        return redirect("superadmin_login")
    deleted = Feedback.objects.filter(pk=feedback_id).delete()
    if deleted[0]:
        messages.success(request, "Feedback deleted.")
    return redirect("superadmin_feedback")


def superadmin_logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("superadmin_login")