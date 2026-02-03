from django.urls import path
from .views import (
    landing_view, register_view, login_view, home_client_view, profile_view, client_update_profile_view, logout_view,
    PasswordChangeView,
    seller_register_view, seller_login_view, home_seller_view, seller_profile_view, seller_update_profile_view, seller_logout_view,
    feedback_view, feedback_delete_view,
    seller_products_view, seller_product_add_view, seller_product_edit_view, seller_product_delete_view,
    seller_notifications_view, seller_notification_mark_read_view,
    client_seller_products_view, wishlist_view, add_to_wishlist_view, remove_from_wishlist_view,
    add_to_cart_view, cart_view, cart_remove_view, checkout_view,
    superadmin_login_view, superadmin_home_view, superadmin_profile_view,
    superadmin_feedback_view, superadmin_feedback_delete_view,
    superadmin_transactions_view,
    superadmin_logout_view,
)

urlpatterns = [
    # Public landing (no auth)
    path('', landing_view, name='landing'),
    # Client URLs
    path('home/', home_client_view, name='home_client'),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('profile/', profile_view, name='profile_client'),
    path('profile/update/', client_update_profile_view, name='client_update_profile'),
    path('profile/password/', PasswordChangeView.as_view(), name='client_password_change'),
    path('logout/', logout_view, name='logout'),
    # Client: sellers, market, cart, wishlist
    path('sellers/<int:seller_id>/products/', client_seller_products_view, name='client_seller_products'),
    path('sellers/<int:seller_id>/cart/add/', add_to_cart_view, name='add_to_cart'),
    path('cart/', cart_view, name='cart'),
    path('cart/remove/<int:product_id>/', cart_remove_view, name='cart_remove'),
    path('cart/checkout/', checkout_view, name='checkout'),
    path('wishlist/', wishlist_view, name='wishlist'),
    path('wishlist/add/<int:product_id>/', add_to_wishlist_view, name='add_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', remove_from_wishlist_view, name='remove_from_wishlist'),
    # Feedback (shared)
    path('feedback/', feedback_view, name='feedback'),
    path('feedback/<int:feedback_id>/delete/', feedback_delete_view, name='feedback_delete'),
    # Seller URLs
    path('seller/register/', seller_register_view, name='seller_register'),
    path('seller/login/', seller_login_view, name='seller_login'),
    path('seller/home/', home_seller_view, name='home_seller'),
    path('seller/profile/', seller_profile_view, name='seller_profile'),
    path('seller/profile/update/', seller_update_profile_view, name='seller_update_profile'),
    path('seller/profile/password/',PasswordChangeView.as_view(),name='seller_password_change'),
    path('seller/logout/', seller_logout_view, name='seller_logout'),
    # Seller product management
    path('seller/products/', seller_products_view, name='seller_products'),
    path('seller/products/add/', seller_product_add_view, name='seller_product_add'),
    path('seller/products/<int:product_id>/edit/', seller_product_edit_view, name='seller_product_edit'),
    path('seller/products/<int:product_id>/delete/', seller_product_delete_view, name='seller_product_delete'),
    path('seller/notifications/', seller_notifications_view, name='seller_notifications'),
    path('seller/notifications/<int:notification_id>/read/', seller_notification_mark_read_view, name='seller_notification_mark_read'),
    # Superadmin
    path('superadmin/login/', superadmin_login_view, name='superadmin_login'),
    path('superadmin/home/', superadmin_home_view, name='superadmin_home'),
    path('superadmin/profile/', superadmin_profile_view, name='superadmin_profile'),
    path('superadmin/profile/password/', PasswordChangeView.as_view(), name='superadmin_password_change'),
    path('superadmin/feedback/', superadmin_feedback_view, name='superadmin_feedback'),
    path('superadmin/feedback/<int:feedback_id>/delete/', superadmin_feedback_delete_view, name='superadmin_feedback_delete'),
    path('superadmin/transactions/', superadmin_transactions_view, name='superadmin_transactions'),
    path('superadmin/logout/', superadmin_logout_view, name='superadmin_logout'),
]