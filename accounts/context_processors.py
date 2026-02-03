from .models import Seller, Notification


def seller_notifications(request):
    """Add seller_unread_notifications count for seller nav (e.g. Notifications (3))."""
    if not request.user.is_authenticated:
        return {"seller_unread_notifications": 0}
    if not Seller.objects.filter(user=request.user).exists():
        return {"seller_unread_notifications": 0}
    seller = Seller.objects.get(user=request.user)
    count = Notification.objects.filter(seller=seller, is_read=False).count()
    return {"seller_unread_notifications": count}
