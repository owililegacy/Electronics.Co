"""eshop urls"""

from django.urls import path
from . import views

from .views import (
    EshopPasswordResetView,
    EshopPasswordResetDoneView,
    EshopPasswordResetConfirmView,
    EshopPasswordResetCompleteView,
)

app_name = 'eshop'

urlpatterns = [
    # FaQ
    path('faq/', views.faq_view, name='faq'),

    # Home
    path('', views.home, name='home'),

    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # User Profile
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),

    # Password Reset
    path(
        'password-reset/',
        EshopPasswordResetView.as_view(),
        name='password_reset'
    ),
    path(
        'password-reset/done/',
        EshopPasswordResetDoneView.as_view(),
        name='password_reset_done'
    ),
    path(
        'password-reset/<uidb64>/<token>/',
        EshopPasswordResetConfirmView.as_view(),
        name='password_reset_confirm'
    ),
    path(
        'password-reset/complete/',
        EshopPasswordResetCompleteView.as_view(),
        name='password_reset_complete'
    ),

    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/<slug:slug>/', views.product_detail, name='product_detail'),

    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/<slug:slug>/', views.category_detail, name='category_detail'),

    # Cart
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:cart_item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:cart_item_id>/', views.update_cart, name='update_cart'),

    # Orders
    path('orders/create/', views.create_order, name='create_order'),
    path('orders/', views.orders_list, name='orders_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),

    # Pages
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),

    # Reviews
    path('products/<slug:product_slug>/reviews/', views.product_reviews, name='product_reviews'),
    path('products/<slug:product_slug>/reviews/add/', views.add_review, name='add_review'),
    path('reviews/', views.all_reviews, name='all_reviews'),
    path('reviews/add/', views.choose_product_for_review, name='choose_product_for_review'),

   # Payment
    path('payment/<int:order_id>/', views.payment_page, name='payment_page'),
    path('payment/mpesa/<int:order_id>/', views.pay_mpesa, name='pay_mpesa'),
    path('payment/mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('order/<int:order_id>/payment/pending/', views.payment_pending, name='payment_pending'),
    path('order/<int:order_id>/confirm-payment/', views.confirm_payment, name='confirm_payment'),
    path('order/<int:order_id>/check-payment/', views.check_payment_status, name='check_payment_status'),

    # Support
    path('support/', views.support_view, name='support'),
]


