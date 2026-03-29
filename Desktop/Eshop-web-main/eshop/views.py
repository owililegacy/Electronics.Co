from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count
from .models import Category, Product, CartItem, Order, OrderItem, ProductReview, Cart, UserProfile, ChatbotQuery
from django.http import Http404, JsonResponse
from .forms import ReviewForm, OrderForm, UserUpdateForm, UserProfileForm
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from .forms import UserRegisterForm, PaymentForm
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_control
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.urls import reverse_lazy
from difflib import SequenceMatcher
from django.utils import timezone
from datetime import timedelta
from django.contrib.sites.shortcuts import get_current_site
import json
import logging

logger = logging.getLogger(__name__)


# ── Chatbot Helper Functions ──────────────────────────────────────────────────

def fuzzy_match(user_input, keywords, threshold=0.6):
    """
    Enhanced matching: if no exact keyword match, find best fuzzy match
    """
    user_input = user_input.lower().strip()
    
    # Exact match (faster)
    for keyword in keywords:
        if keyword in user_input or user_input in keyword:
            return True
    
    # Fuzzy match for typos
    for keyword in keywords:
        ratio = SequenceMatcher(None, user_input, keyword).ratio()
        if ratio >= threshold:
            return True
    return False


def get_conversation_history(user, limit=5):
    """
    Get recent conversation history for context-aware responses
    """
    if not user or not user.is_authenticated:
        return []
    
    past_messages = ChatbotQuery.objects.filter(user=user).order_by('-created')[:limit]
    return list(reversed(past_messages))


def get_user_viewed_products(user):
    """
    Get products viewed by user (based on orders and reviews)
    """
    if not user or not user.is_authenticated:
        return Product.objects.none()
    
    # Get products from user's orders
    ordered_products = Product.objects.filter(orderitem__order__user=user).distinct()
    
    # Get products user reviewed
    reviewed_products = Product.objects.filter(reviews__user=user).distinct()
    
    return (ordered_products | reviewed_products).distinct()


def get_smart_recommendations(user):
    """
    AI-powered product recommendations based on user profile
    """
    if not user or not user.is_authenticated:
        return Product.objects.filter(available=True)[:5]
    
    # Get categories user interacted with
    user_categories = Category.objects.filter(
        products__orderitem__order__user=user
    ).distinct()
    
    if user_categories:
        # Recommend from same categories, excluding what they've bought
        viewed = get_user_viewed_products(user)
        recommendations = Product.objects.filter(
            category__in=user_categories,
            available=True
        ).exclude(id__in=viewed.values_list('id')).distinct()[:8]
        
        if recommendations:
            return recommendations
    
    # Fallback: popular products
    return Product.objects.filter(available=True).annotate(
        review_count=Count('reviews')
    ).order_by('-review_count')[:5]


def format_product_with_stock(product):
    """
    Format product info with stock availability
    """
    stock_status = "✅ In Stock" if product.stock > 0 else "🔴 Out of Stock"
    return f"<b>{product.name}</b> — KES {product.price:,} {stock_status}"


# ── Auth Views ────────────────────────────────────────────────────────────────

@cache_control(no_cache=True, no_store=True, must_revalidate=True, max_age=0)
def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now login.')
            return redirect('eshop:login')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserRegisterForm()
    return render(request, 'eshop/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('eshop:home')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'eshop/login.html', {'form': form})


@cache_control(no_cache=True, no_store=True, must_revalidate=True, max_age=0)
def logout_view(request):
    # Clear all existing messages from previous interactions (payments, M-Pesa, etc.)
    from django.contrib.messages import get_messages
    storage = get_messages(request)
    for _ in list(storage):
        pass  # Consume all messages to clear them
    
    logout(request)
    messages.success(request, 'You have been logged out!')
    return redirect('eshop:home')


# ── General Views ─────────────────────────────────────────────────────────────

def home(request):
    categories = Category.objects.all()
    return render(request, 'eshop/home.html', {'categories': categories})


def product_list(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category')
    price_min = request.GET.get('price_min')
    price_max = request.GET.get('price_max')
    sort = request.GET.get('sort', 'name')
    available_only = request.GET.get('available_only') == 'on'

    products = Product.objects.filter(available=True)
    categories = Category.objects.all()

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
    if category_id:
        products = products.filter(category_id=category_id)
    if price_min:
        products = products.filter(price__gte=price_min)
    if price_max:
        products = products.filter(price__lte=price_max)

    if sort == 'price':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created')
    else:
        products = products.order_by('name')

    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)

    context = {
        'products': products_page,
        'categories': categories,
        'query': query,
        'category_id': category_id,
        'price_min': price_min,
        'price_max': price_max,
        'sort': sort,
        'available_only': available_only,
    }
    return render(request, 'eshop/product_list.html', context)


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, available=True)
    return render(request, 'eshop/product_detail.html', {'product': product})


def category_list(request):
    categories = Category.objects.all()
    return render(request, 'eshop/category_list.html', {'categories': categories})


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(category=category, available=True)
    return render(request, 'eshop/category_detail.html', {'category': category, 'products': products})


# ── Cart Views ────────────────────────────────────────────────────────────────

@login_required(login_url='eshop:login')
def view_cart(request):
    try:
        cart = request.user.cart
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)
    cart_items = cart.items.all()
    return render(request, 'eshop/cart.html', {'cart_items': cart_items, 'cart': cart})


@login_required(login_url='eshop:login')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            messages.error(request, 'Quantity must be at least 1.')
            return redirect('eshop:product_detail', slug=product.slug)
    except (ValueError, TypeError):
        messages.error(request, 'Invalid quantity. Please enter a valid number.')
        return redirect('eshop:product_detail', slug=product.slug)
    
    cart_item, item_created = CartItem.objects.get_or_create(cart=cart, product=product)
    if item_created:
        cart_item.quantity = quantity
    else:
        cart_item.quantity += quantity
    cart_item.save()
    return redirect('eshop:view_cart')


@login_required
def remove_from_cart(request, cart_item_id):
    try:
        cart_item = CartItem.objects.get(pk=cart_item_id, cart__user=request.user)
        cart_item.delete()
    except CartItem.DoesNotExist:
        raise Http404("Cart item does not exist")
    return redirect('eshop:view_cart')


@login_required
def update_cart(request, cart_item_id):
    try:
        cart_item = CartItem.objects.get(pk=cart_item_id, cart__user=request.user)
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid quantity. Please enter a valid number.')
            return redirect('eshop:view_cart')
        
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()
    except CartItem.DoesNotExist:
        raise Http404("Cart item does not exist")
    return redirect('eshop:view_cart')


# ── Order Views ───────────────────────────────────────────────────────────────

@login_required(login_url='eshop:login')
@cache_control(no_cache=True, no_store=True, must_revalidate=True, max_age=0)
def create_order(request):
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        messages.error(request, 'Your cart is empty.')
        return redirect('eshop:product_list')

    if not cart.items.exists():
        messages.error(request, 'Your cart is empty. Add products before placing an order.')
        return redirect('eshop:view_cart')

    # Get user's profile for auto-filling form
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        profile = None

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Split full_name into first_name and last_name
            full_name = form.cleaned_data.get('full_name', '').strip()
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            order = Order.objects.create(
                user=request.user,
                first_name=first_name,
                last_name=last_name,
                email=form.cleaned_data['email'],
                address=form.cleaned_data['address'],
                postal_code=form.cleaned_data['postal_code'],
                city=form.cleaned_data['city'],
            )
            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    price=item.product.price,
                    quantity=item.quantity,
                )
            cart.items.all().delete()
            return redirect('eshop:payment_page', order_id=order.id)
    else:
        # Pre-fill form with user profile and user data
        initial_data = {
            'email': request.user.email,
        }
        
        # Try to get full_name from profile first, then from user
        if profile and profile.full_name:
            initial_data['full_name'] = profile.full_name
        elif request.user.first_name or request.user.last_name:
            full_name = f"{request.user.first_name} {request.user.last_name}".strip()
            initial_data['full_name'] = full_name
        
        if profile:
            if profile.address:
                initial_data['address'] = profile.address
            if profile.city:
                initial_data['city'] = profile.city
            if profile.postal_code:
                initial_data['postal_code'] = profile.postal_code
        
        form = OrderForm(initial=initial_data)

    return render(request, 'eshop/create_order.html', {'form': form, 'cart': cart})


@login_required(login_url='eshop:login')
def payment_select(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.order = order
            payment.pay_with = f"ORDER-{order.id}"
            payment.status = 'PENDING'
            payment.save()
            messages.success(request, 'Payment details submitted! Please make your payment and await confirmation.')
            return redirect('eshop:order_detail', order_id=order.id)
    else:
        form = PaymentForm()
    return render(request, 'eshop/payment_select.html', {'form': form, 'order': order})


@login_required(login_url='eshop:login')
def orders_list(request):
    orders = Order.objects.filter(user=request.user).order_by('-created')
    return render(request, 'eshop/orders_list.html', {'orders': orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    tracking_steps = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
    ]
    return render(request, 'eshop/order_detail.html', {'order': order, 'tracking_steps': tracking_steps})


# ── Review Views ──────────────────────────────────────────────────────────────

def product_reviews(request, product_slug):
    product = get_object_or_404(Product, slug=product_slug)
    reviews = ProductReview.objects.filter(product=product).order_by('-created')
    return render(request, 'eshop/product_reviews.html', {'product': product, 'reviews': reviews})


@login_required(login_url='eshop:login')
def add_review(request, product_slug):
    product = get_object_or_404(Product, slug=product_slug)
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
            return redirect('eshop:product_detail', slug=product.slug)
    else:
        form = ReviewForm()
    return render(request, 'eshop/add_review.html', {'product': product, 'form': form})


def all_reviews(request):
    reviews = ProductReview.objects.all().order_by('-created')
    return render(request, 'eshop/all_reviews.html', {'reviews': reviews})


def choose_product_for_review(request):
    products = Product.objects.filter(available=True)
    return render(request, 'eshop/choose_product_for_review.html', {'products': products})


# ── Static Pages ──────────────────────────────────────────────────────────────

def support_view(request):
    return render(request, 'eshop/support.html')


def about_view(request):
    return render(request, 'eshop/about.html')



# --------------------------------Contact-view
@csrf_exempt
def contact_view(request):
    message = request.GET.get('message', '') or request.POST.get('message', '')
    user = request.user if request.user.is_authenticated else None

    if not message:
        return JsonResponse({'response': 'Hi! 👋 Welcome to E-SHOP support. How can I help you today?'})

    msg = message.lower().strip()
    response_text = None
    was_answered = True
    
    # Get conversation history for context
    history = get_conversation_history(user, limit=3)

    # Define keyword categories with fuzzy matching support
    greeting_kw = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy', 'greetings', 'salaam']
    help_kw = ['help', 'what can you do', 'options', 'menu', 'commands', 'features', 'available', 'tell me more', 'guide']
    product_kw = [
        'product', 'item', 'sell', 'stock', 'available', 'buy', 'purchase', 'have', 'price', 'cost', 
        'how much', 'cheap', 'affordable', 'expensive', 'discount', 'suggest',
        # Laptop brands & keywords
        'laptop', 'laptops', 'macbook', 'hp', 'dell', 'lenovo', 'asus', 'acer', 'msi', 'alienware', 
        'toshiba', 'sony', 'vaio', 'surface', 'book', 'notebook', 'computer', 'pc',
        # Phone brands & keywords
        'phone', 'phones', 'iphone', 'samsung', 'galaxy', 'pixel', 'xiaomi', 'huawei', 'oneplus', 
        'motorola', 'nokia', 'realme', 'oppo', 'vivo', 'nothing', 'fone', 'mobile',
        # Tablet keywords
        'tablet', 'tablets', 'ipad', 'tab', 'pad',
        # Audio keywords
        'headphone', 'headphones', 'earphone', 'earphones', 'airpod', 'speaker', 'audio', 'beats', 
        'bose', 'sony', 'jbl', 'skullcandy', 'soundfree',
        # Watch keywords
        'watch', 'smartwatch', 'wearable', 'apple watch', 'garmin', 'fitbit', 'band', 'bracelet',
        # Gaming & console
        'gaming', 'console', 'playstation', 'xbox', 'nintendo', 'retro', 'psp', 'game', 'gamer',
        # Accessories
        'monitor', 'keyboard', 'mouse', 'charger', 'cable', 'adapter', 'usb', 'power', 'charging',
        'display', 'screen', 'peripherals', 'accessory', 'accessories',
        # General search terms
        'best', 'top', 'popular', 'trending', 'new', 'latest', 'what', 'which', 'any'
    ]
    review_kw = ['review', 'rating', 'feedback', 'opinion', 'recommend', 'rate', 'score', 'star', 'best seller']
    delivery_kw = ['delivery', 'shipping', 'ship', 'arrive', 'arrival', 'how long', 'when will', 'dispatch', 'package', 'track', 'courier', 'fast', 'express']
    payment_kw = ['payment', 'pay', 'mpesa', 'mobile money', 'card', 'bank', 'transfer', 'checkout', 'method', 'secure', 'ssl', 'how to pay']
    order_kw = ['order', 'track', 'status', 'my order', 'placed', 'history', 'purchase', 'pending', 'processing', 'shipped', 'delivered']
    return_kw = ['return', 'refund', 'exchange', 'warranty', 'broken', 'damaged', 'defect', 'issue', 'problem', 'complaint', 'not working']
    account_kw = ['account', 'login', 'register', 'sign up', 'password', 'profile', 'forgot', 'reset', 'unlock', 'access', 'username']
    cart_kw = ['cart', 'basket', 'add to cart', 'remove', 'quantity', 'checkout', 'shop', 'buy', 'add items']
    contact_kw = ['contact', 'email', 'phone', 'call', 'reach', 'support', 'talk to', 'human', 'agent', 'help desk']
    about_kw = ['about', 'who are you', 'company', 'store', 'eshop', 'e-shop', 'mission', 'vision']
    goodbye_kw = ['bye', 'goodbye', 'thanks', 'thank you', 'cheers', 'great', 'perfect', 'awesome', 'nice', 'see you']
    deal_kw = ['deal', 'discount', 'promo', 'sale', 'offer', 'coupon', 'code', 'save', 'free']

    # GREETING
    if fuzzy_match(msg, greeting_kw):
        response_text = 'Hi there! 👋 Welcome to E-SHOP. I can help you with products, orders, delivery, payments, and more. What would you like to know?'

    # HELP & MENU
    elif fuzzy_match(msg, help_kw):
        response_text = (
            "Here's what I can help with:\n"
            "🛒 <b>Products</b> — search by name or ask for recommendations\n"
            "📦 <b>Orders</b> — tracking, status, how to order\n"
            "🚚 <b>Delivery</b> — shipping times, costs & tracking\n"
            "💳 <b>Payment</b> — payment methods & security\n"
            "↩️ <b>Returns & Refunds</b> — our policy & process\n"
            "⭐ <b>Reviews</b> — customer feedback & ratings\n"
            "👤 <b>Account</b> — login, register, passwords\n"
            "🛍️ <b>Shopping</b> — cart, checkout, deals\n"
            "📞 <b>Contact</b> — reach our support team\n\n"
            "Just ask naturally, e.g. <i>\"Do you have iPhones?\"</i>"
        )

    # PRODUCT SEARCH - Direct search without recommendations
    elif fuzzy_match(msg, product_kw):
        # Direct product search with fuzzy matching
        term_map = {
            'laptop':    ['laptop', 'macbook', 'hp', 'dell', 'lenovo', 'asus', 'acer', 'msi', 'alienware', 'notebook', 'computer', 'ultrabook', 'book', 'spectre', 'pavilion', 'thinkpad'],
            'phone':     ['phone', 'iphone', 'samsung', 'galaxy', 'pixel', 'xiaomi', 'huawei', 'oneplus', 'nothing', 'motorola', 'nokia', 'realme', 'oppo', 'vivo', 'fone', 'mobile'],
            'tablet':    ['tablet', 'ipad', 'tab', 'pad'],
            'headphone': ['headphone', 'earphone', 'airpod', 'soundfree', 'audio', 'beats', 'bose', 'sony', 'jbl', 'speaker', 'skullcandy'],
            'watch':     ['watch', 'smartwatch', 'wearable', 'garmin', 'fitbit', 'apple watch', 'band', 'bracelet'],
            'gaming':    ['gaming', 'console', 'playstation', 'xbox', 'nintendo', 'retro', 'psp', 'game', 'gamer'],
            'accessories': ['mouse', 'keyboard', 'monitor', 'charger', 'cable', 'adapter', 'power', 'usb', 'display', 'screen'],
        }
        
        search_words = [w for w in msg.split() if len(w) > 2]
        expanded = list(search_words)
        
        # Add category synonyms
        for word in search_words:
            for key, synonyms in term_map.items():
                if fuzzy_match(word, [key]):
                    expanded.extend(synonyms)
        
        # Search in database products
        matches = []
        for word in expanded:
            # Direct product name matching
            matches.extend(list(Product.objects.filter(name__icontains=word, available=True)))
            # Also search in category name
            matches.extend(list(Product.objects.filter(category__name__icontains=word, available=True)))
        
        seen = set()
        unique = []
        for p in matches:
            if p.id not in seen:
                seen.add(p.id)
                unique.append(p)
        
        if unique:
            lines = '\n'.join(f'• {format_product_with_stock(p)}' for p in unique[:15])
            response_text = f"Found {len(unique)} product(s):\n{lines}\n\n<a href='/products/' style='color:#ff6600;'>Browse all →</a>"
        else:
            # If no matches, show latest products
            all_available = Product.objects.filter(available=True).order_by('-created')[:15]
            if all_available:
                lines = '\n'.join(f'• {format_product_with_stock(p)}' for p in all_available)
                response_text = f"No exact match for that. Here are our latest products:\n{lines}\n\n<a href='/products/' style='color:#ff6600;'>More products →</a>"
            else:
                response_text = "Browse our full catalog at <a href='/products/' style='color:#ff6600;'>Products page</a>."

    # REVIEWS & RATINGS
    elif fuzzy_match(msg, review_kw):
        recent = ProductReview.objects.select_related('product').order_by('-created')[:8]
        if recent:
            lines = '\n'.join(f'✅ <b>{r.product.name}</b>: {"⭐" * int(r.rating)} | <i>"{r.comment[:50]}..."</i>' for r in recent)
            response_text = f"⭐ <b>Recent Customer Reviews:</b>\n{lines}\n\n<a href='/reviews/' style='color:#ff6600;'>See all →</a>"
        else:
            response_text = "No reviews yet! Be the first — <a href='/reviews/add/' style='color:#ff6600;'>add a review →</a>"

    # DELIVERY & SHIPPING
    elif fuzzy_match(msg, delivery_kw):
        response_text = (
            "🚚 <b>Delivery Information:</b>\n"
            "⚡ <b>Standard:</b> 2–3 business days (Free)\n"
            "🚀 <b>Express:</b> Next day (Premium)\n"
            "🎁 <b>FREE shipping</b> on orders over KES 5,000!\n"
            "🇰🇪 Nationwide delivery\n"
            "📍 Real-time tracking available\n\n"
            "After payment, you'll get a tracking number instantly!"
        )

    # PAYMENT INFORMATION
    elif fuzzy_match(msg, payment_kw):
        response_text = (
            "💳 <b>Secure Payment Methods:</b>\n"
            "📱 <b>M-Pesa</b> (STK Push) — Quick & Safe ✅\n"
            "🔒 SSL Encrypted\n"
            "✨ No extra charges\n"
            "⚡ Instant confirmation\n\n"
            "<b>How to pay:</b>\n"
            "1. Add items to cart\n"
            "2. Go to checkout\n"
            "3. Enter phone number\n"
            "4. Confirm M-Pesa PIN\n"
            "✅ Done!"
        )

    # ORDERS & TRACKING
    elif fuzzy_match(msg, order_kw):
        if user and user.is_authenticated:
            order_count = Order.objects.filter(user=user).count()
            recent_orders = Order.objects.filter(user=user).order_by('-created')[:3]
            order_status = '\n'.join(f"• Order #{o.id}: {o.status}" for o in recent_orders) if recent_orders else "No orders yet"
            
            response_text = (
                f"📦 <b>Your Orders ({order_count})</b>\n"
                f"{order_status}\n\n"
                f"<a href='/orders/' style='color:#ff6600;'>View all orders →</a>\n\n"
                f"Status meanings:\n"
                f"🟡 Pending — Confirmed\n"
                f"🟠 Processing — Being prepared\n"
                f"🔵 Shipped — On the way\n"
                f"🟢 Delivered — Completed"
            )
        else:
            response_text = (
                "📦 <b>Track Your Orders:</b>\n"
                "1. <a href='/login/' style='color:#ff6600;'>Login →</a>\n"
                "2. Click 'My Orders'\n"
                "3. See status & tracking\n\n"
                "No account? <a href='/register/' style='color:#ff6600;'>Register now →</a>"
            )

    # RETURNS & REFUNDS
    elif fuzzy_match(msg, return_kw):
        response_text = (
            "↩️ <b>Returns & Refunds Policy:</b>\n"
            "✅ <b>30-day money-back guarantee</b>\n"
            "📦 Original condition & packaging\n"
            "🚚 Free returns on defects\n"
            "🆘 Damaged? Contact us ASAP\n\n"
            "📧 <b>support@eshop.com</b>\n"
            "⏱️ Refunds: 5–7 business days"
        )

    # ACCOUNT & LOGIN
    elif fuzzy_match(msg, account_kw):
        if user and user.is_authenticated:
            response_text = (
                f"👤 <b>Welcome, {user.username}!</b> 🎉\n"
                f"<a href='/profile/' style='color:#ff6600;'>View Profile →</a>\n"
                f"<a href='/orders/' style='color:#ff6600;'>My Orders →</a>\n"
                f"<a href='/password-reset/' style='color:#ff6600;'>Change Password →</a>"
            )
        else:
            response_text = (
                "👤 <b>Account Options:</b>\n"
                "• <a href='/login/' style='color:#ff6600;'>Login →</a>\n"
                "• <a href='/register/' style='color:#ff6600;'>Sign Up →</a>\n"
                "• <a href='/password-reset/' style='color:#ff6600;'>Forgot Password →</a>\n\n"
                "Join E-SHOP for exclusive benefits! 🎁"
            )

    # SHOPPING & CART
    elif fuzzy_match(msg, cart_kw):
        if user and user.is_authenticated:
            try:
                cart = Cart.objects.get(user=user)
                item_count = cart.items.count()
                total = cart.get_total_price()
                response_text = (
                    f"🛒 <b>Your Cart</b>\n"
                    f"Items: {item_count} | Total: KES {total:,}\n\n"
                    f"<a href='/cart/' style='color:#ff6600;'>View Cart →</a>\n"
                    f"<a href='/orders/create/' style='color:#ff6600;'>Checkout →</a>\n\n"
                    f"💡 Tip: Orders over KES 5,000 get FREE shipping!"
                )
            except Cart.DoesNotExist:
                response_text = "Your cart is empty. <a href='/products/' style='color:#ff6600;'>Start shopping →</a>"
        else:
            response_text = (
                "🛒 <b>Shopping Guide:</b>\n"
                "1. Browse <a href='/products/' style='color:#ff6600;'>products →</a>\n"
                "2. Click 'Add to Cart'\n"
                "3. Review your cart\n"
                "4. Checkout & pay\n\n"
                "💡 Orders over KES 5,000 = FREE shipping!"
            )

    # CONTACT & SUPPORT
    elif fuzzy_match(msg, contact_kw):
        response_text = (
            "📞 <b>Contact Our Support:</b>\n"
            "📧 Email: <b>support@eshop.com</b>\n"
            "🌐 <a href='/contact/' style='color:#ff6600;'>Contact Form →</a>\n"
            "🆘 <a href='/support/' style='color:#ff6600;'>Help Center →</a>\n\n"
            "⏱️ Response time: Within 24 hours\n"
            "We're here to help! 💪"
        )

    # ABOUT COMPANY
    elif fuzzy_match(msg, about_kw):
        response_text = (
            "ℹ️ <b>About E-SHOP Kenya:</b>\n"
            "🏆 Leading online electronics store\n"
            "✅ Premium products & competitive prices\n"
            "✅ Fast nationwide delivery\n"
            "✅ Secure M-Pesa payments\n"
            "✅ 30-day guarantee\n"
            "✅ Award-winning customer service\n\n"
            "<a href='/about/' style='color:#ff6600;'>Learn more →</a>"
        )

    # THANK YOU & GOODBYE
    elif fuzzy_match(msg, goodbye_kw):
        response_text = "Thank you for choosing E-SHOP! 😊 Come back soon. 🛒"

    # PROMOTIONS & DEALS
    elif fuzzy_match(msg, deal_kw):
        response_text = (
            "🎉 <b>Special Offers & Deals:</b>\n"
            "💰 <b>FREE shipping</b> on orders KES 5,000+\n"
            "⭐ <b>New products</b> with special pricing\n"
            "🎁 <b>Bundle deals</b> available\n"
            "📱 Follow us for <b>flash sales!</b>\n\n"
            "<a href='/products/' style='color:#ff6600;'>Shop now →</a>"
        )

    # FALLBACK — learn from unanswered questions
    if response_text is None:
        was_answered = False
        response_text = (
            "🤔 I'm learning! I didn't quite understand that.\n\n"
            "<b>What I can help with:</b>\n"
            "• Products (e.g., <i>'Show me iPhones'</i>)\n"
            "• Orders & tracking\n"
            "• Delivery & payment\n"
            "• Returns & refunds\n"
            "• Account help\n\n"
            "Type <b>help</b> for all options or <a href='/support/' style='color:#ff6600;'>contact support</a>"
        )

    # SAVE CONVERSATION & TRACK BEHAVIOR
    ChatbotQuery.objects.create(
        message=message,
        response=response_text,
        user=user,
        was_answered=was_answered
    )

    return JsonResponse({'response': response_text})


# ── Password Reset ────────────────────────────────────────────────────────────

class EshopPasswordResetView(PasswordResetView):
    template_name = 'eshop/password_reset.html'
    email_template_name = 'eshop/password_reset_email.html'
    subject_template_name = 'eshop/password_reset_subject.txt'
    success_url = reverse_lazy('eshop:password_reset_done')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        # Add protocol and domain for email template
        context['protocol'] = 'https' if request.is_secure() else 'http'
        context['domain'] = get_current_site(request).domain
        return context


class EshopPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'eshop/password_reset_done.html'


class EshopPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'eshop/password_reset_confirm.html'
    success_url = reverse_lazy('eshop:password_reset_complete')


class EshopPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'eshop/password_reset_complete.html'


# ── M-Pesa Payment ────────────────────────────────────────────────────────────

@login_required(login_url='eshop:login')
def payment_page(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(request, 'eshop/payment.html', {'order': order})


@login_required(login_url='eshop:login')
def pay_mpesa(request, order_id):
    from .mpesa import stk_push
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if request.method == 'POST':
        phone = request.POST.get('phone_number', '').strip()
        amount = order.get_total_price()
        result = stk_push(phone, amount, order_id)

        if result.get('ResponseCode') == '0':
            messages.success(request, '✅ M-Pesa prompt sent! Enter your PIN on your phone.')
            return redirect('eshop:payment_pending', order_id=order.id)
        else:
            error_msg = result.get('errorMessage') or result.get('ResponseDescription', 'Unknown error')
            messages.error(request, f'M-Pesa request failed: {error_msg}. Please try again.')
            return redirect('eshop:payment_page', order_id=order.id)

    return redirect('eshop:payment_page', order_id=order.id)


@csrf_exempt
def mpesa_callback(request):
    logger.debug(f"M-Pesa callback received via {request.method}")
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            logger.debug(f"M-Pesa callback data received")
            result = data.get('Body', {}).get('stkCallback', {})
            if result.get('ResultCode') == 0:
                metadata = result.get('CallbackMetadata', {}).get('Item', [])
                account_ref = next(
                    (item['Value'] for item in metadata if item['Name'] == 'AccountReference'), None
                )
                logger.info(f"M-Pesa payment successful for account reference: {account_ref}")
                if account_ref:
                    try:
                        order_id = account_ref.replace('Order', '')
                        Order.objects.filter(pk=int(order_id)).update(paid=True, status='PROCESSING')
                        logger.info(f"Order {order_id} marked as paid!")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid order ID format: {account_ref}. Error: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error processing M-Pesa callback: {e}")
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})


@login_required(login_url='eshop:login')
def payment_pending(request, order_id):
    
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(request, 'eshop/payment_pending.html', {'order': order})


@login_required(login_url='eshop:login')
def confirm_payment(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if request.method == 'POST':
        order.paid = True
        order.status = 'PROCESSING'
        order.save()
        messages.success(request, 'Payment confirmed! Your order is being processed.')
        return redirect('eshop:order_detail', order_id=order.id)
    return redirect('eshop:payment_pending', order_id=order.id)

@login_required(login_url='eshop:login')
def check_payment_status(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return JsonResponse({'paid': order.paid})


def faq_view(request):
    return render(request, 'eshop/faq.html')


# ── User Profile Views ────────────────────────────────────────────────────────

@login_required(login_url='eshop:login')
def profile_view(request):
    """Display user profile"""
    user = request.user
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
    
    context = {
        'user': user,
        'profile': profile,
    }
    return render(request, 'eshop/profile_view.html', context)


@login_required(login_url='eshop:login')
@cache_control(no_cache=True, no_store=True, must_revalidate=True, max_age=0)
def profile_edit(request):
    """Edit user profile"""
    user = request.user
    
    # Ensure user has a profile
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('eshop:profile_view')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserUpdateForm(instance=user)
        profile_form = UserProfileForm(instance=profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'profile': profile,
    }
    return render(request, 'eshop/profile_edit.html', context)