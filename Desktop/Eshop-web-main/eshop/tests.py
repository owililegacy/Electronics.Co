# eshop/tests.py

from django.test import TestCase
from django.contrib.auth.models import User
from .models import Product, Category, Cart, Order, OrderItem

# 1. Testing User Model
class UserModelTest(TestCase):

    def test_create_user_with_required_fields(self):
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='hashedpassword'
        )
        self.assertIsNotNone(user.id)
        self.assertEqual(user.username, 'testuser')

    def test_user_requires_username(self):
        with self.assertRaises(Exception):
            User.objects.create_user(username='', password='pass')


# 2. Testing Product Model
class ProductModelTest(TestCase):

    def setUp(self):
        self.category = Category.objects.create(name='Electronics', slug='electronics')

    def test_create_product(self):
        product = Product.objects.create(
            category=self.category,
            name='iPhone 16',
            slug='iphone-16',
            price=1200.00,
        )
        self.assertIsNotNone(product.id)
        self.assertEqual(str(product), 'iPhone 16')

    def test_product_requires_price(self):
        with self.assertRaises(Exception):
            Product.objects.create(
                category=self.category,
                name='Bad Product',
                slug='bad-product',
                price=None,
            )


# 3. Testing Order Model
class OrderModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='buyer', password='pass')
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            category=self.category,
            name='Samsung S24',
            slug='samsung-s24',
            price=1190.00,
        )

    def test_order_total_price(self):
        order = Order.objects.create(
            user=self.user,
            first_name='Test',
            last_name='User',
            email='test@example.com',
            address='123 Street',
            postal_code='00100',
            city='Nairobi',
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            price=self.product.price,
            quantity=2,
        )
        self.assertEqual(order.get_total_price(), 2380.00)

    def test_order_default_status_is_pending(self):
        order = Order.objects.create(
            user=self.user,
            first_name='Test', last_name='User',
            email='test@example.com',
            address='123 Street', postal_code='00100', city='Nairobi',
        )
        self.assertEqual(order.status, 'PENDING')
        self.assertFalse(order.paid)


        # eshop/tests.py  — add below the existing tests

from django.test import TestCase, Client
from django.urls import reverse
from .models import Product, Category

# 2. Testing Product Retrieval (equivalent of GET /api/products)
class ProductListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(
            name='Electronics',
            slug='electronics'
        )
        # Create some test products
        Product.objects.create(
            category=self.category,
            name='iPhone 16',
            slug='iphone-16',
            price=1200.00,
            available=True,
        )
        Product.objects.create(
            category=self.category,
            name='Samsung S24',
            slug='samsung-s24',
            price=1190.00,
            available=True,
        )

    def test_product_list_returns_200(self):
        # equivalent of: expect(res.status).toBe(200)
        response = self.client.get(reverse('eshop:product_list'))
        self.assertEqual(response.status_code, 200)

    def test_product_list_contains_products(self):
        # equivalent of: expect(res.body).toBeInstanceOf(Array)
        response = self.client.get(reverse('eshop:product_list'))
        self.assertIn('products', response.context)
        self.assertEqual(response.context['products'].paginator.count, 2)

    def test_product_list_uses_correct_template(self):
        response = self.client.get(reverse('eshop:product_list'))
        self.assertTemplateUsed(response, 'eshop/product_list.html')

    def test_product_search_filters_results(self):
        # Test the search/query feature
        response = self.client.get(reverse('eshop:product_list'), {'q': 'iPhone'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['products'].paginator.count, 1)

    def test_unavailable_products_not_shown(self):
        Product.objects.create(
            category=self.category,
            name='Hidden Product',
            slug='hidden-product',
            price=500.00,
            available=False,   # <-- not available
        )
        response = self.client.get(reverse('eshop:product_list'))
        # Should still only show 2 (the available ones)
        self.assertEqual(response.context['products'].paginator.count, 2)

        # eshop/tests.py — Integration Testing Examples

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Product, Category, Cart, CartItem, Order, OrderItem, ProductReview


# ── 1. User Registration & Login Flow ─────────────────────────────────────────

class AuthIntegrationTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_user_can_register(self):
        response = self.client.post(reverse('eshop:register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        # Should redirect to login after success
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_user_can_login(self):
        User.objects.create_user(username='testuser', password='StrongPass123!')
        response = self.client.post(reverse('eshop:login'), {
            'username': 'testuser',
            'password': 'StrongPass123!',
        })
        # Should redirect to home after login
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('eshop:home'))

    def test_wrong_password_fails_login(self):
        User.objects.create_user(username='testuser', password='StrongPass123!')
        response = self.client.post(reverse('eshop:login'), {
            'username': 'testuser',
            'password': 'WrongPassword',
        })
        # Should stay on login page with error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid')

    def test_user_can_logout(self):
        User.objects.create_user(username='testuser', password='StrongPass123!')
        self.client.login(username='testuser', password='StrongPass123!')
        response = self.client.get(reverse('eshop:logout'))
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_user_redirected_from_cart(self):
        response = self.client.get(reverse('eshop:view_cart'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)


# ── 2. Product Browsing Flow ──────────────────────────────────────────────────

class ProductBrowsingIntegrationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            category=self.category,
            name='iPhone 16 Pro',
            slug='iphone-16-pro',
            price=1200.00,
            available=True,
        )

    def test_home_page_loads(self):
        response = self.client.get(reverse('eshop:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'eshop/home.html')

    def test_product_list_page_loads(self):
        response = self.client.get(reverse('eshop:product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'iPhone 16 Pro')

    def test_product_detail_page_loads(self):
        response = self.client.get(
            reverse('eshop:product_detail', kwargs={'slug': self.product.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'iPhone 16 Pro')
        self.assertContains(response, '1200')

    def test_category_page_shows_products(self):
        response = self.client.get(
            reverse('eshop:category_detail', kwargs={'slug': self.category.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'iPhone 16 Pro')

    def test_search_returns_matching_products(self):
        response = self.client.get(reverse('eshop:product_list'), {'q': 'iPhone'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'iPhone 16 Pro')

    def test_search_returns_no_results_for_unknown(self):
        response = self.client.get(reverse('eshop:product_list'), {'q': 'xyznotexist'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['products'].paginator.count, 0)

    def test_unavailable_product_returns_404(self):
        unavailable = Product.objects.create(
            category=self.category,
            name='Old Product',
            slug='old-product',
            price=100.00,
            available=False,
        )
        response = self.client.get(
            reverse('eshop:product_detail', kwargs={'slug': unavailable.slug})
        )
        self.assertEqual(response.status_code, 404)


# ── 3. Cart Flow ──────────────────────────────────────────────────────────────

class CartIntegrationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='buyer', password='StrongPass123!'
        )
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            category=self.category,
            name='Samsung S24',
            slug='samsung-s24',
            price=1190.00,
            available=True,
        )
        self.client.login(username='buyer', password='StrongPass123!')

    def test_add_product_to_cart(self):
        response = self.client.post(
            reverse('eshop:add_to_cart', kwargs={'product_id': self.product.id}),
            {'quantity': 1}
        )
        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 1)

    def test_cart_total_price_is_correct(self):
        self.client.post(
            reverse('eshop:add_to_cart', kwargs={'product_id': self.product.id}),
            {'quantity': 2}
        )
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.get_total_price, 2380.00)

    def test_remove_item_from_cart(self):
        self.client.post(
            reverse('eshop:add_to_cart', kwargs={'product_id': self.product.id}),
            {'quantity': 1}
        )
        cart = Cart.objects.get(user=self.user)
        cart_item = cart.items.first()
        response = self.client.post(
            reverse('eshop:remove_from_cart', kwargs={'cart_item_id': cart_item.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(cart.items.count(), 0)

    def test_update_cart_quantity(self):
        self.client.post(
            reverse('eshop:add_to_cart', kwargs={'product_id': self.product.id}),
            {'quantity': 1}
        )
        cart = Cart.objects.get(user=self.user)
        cart_item = cart.items.first()
        self.client.post(
            reverse('eshop:update_cart', kwargs={'cart_item_id': cart_item.id}),
            {'quantity': 3}
        )
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 3)

    def test_empty_cart_blocks_order(self):
        response = self.client.post(reverse('eshop:create_order'), {
            'first_name': 'Test', 'last_name': 'User',
            'email': 'test@example.com', 'address': '123 Street',
            'postal_code': '00100', 'city': 'Nairobi',
        })
        # Should redirect back to cart, not create an order
        self.assertRedirects(response, reverse('eshop:view_cart'))
        self.assertEqual(Order.objects.count(), 0)


# ── 4. Order Placement Flow ───────────────────────────────────────────────────

class OrderIntegrationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='buyer', password='StrongPass123!'
        )
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            category=self.category,
            name='MacBook Pro M4',
            slug='macbook-pro-m4',
            price=2700.00,
            available=True,
        )
        self.client.login(username='buyer', password='StrongPass123!')
        # Add product to cart
        self.client.post(
            reverse('eshop:add_to_cart', kwargs={'product_id': self.product.id}),
            {'quantity': 1}
        )

    def test_order_is_created_with_correct_items(self):
        self.client.post(reverse('eshop:create_order'), {
            'first_name': 'John', 'last_name': 'Doe',
            'email': 'john@example.com', 'address': '75 Tenges',
            'postal_code': '30401', 'city': 'Nakuru',
        })
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().product, self.product)

    def test_order_total_price_is_correct(self):
        self.client.post(reverse('eshop:create_order'), {
            'first_name': 'John', 'last_name': 'Doe',
            'email': 'john@example.com', 'address': '75 Tenges',
            'postal_code': '30401', 'city': 'Nakuru',
        })
        order = Order.objects.first()
        self.assertEqual(order.get_total_price(), 2700.00)

    def test_cart_is_cleared_after_order(self):
        self.client.post(reverse('eshop:create_order'), {
            'first_name': 'John', 'last_name': 'Doe',
            'email': 'john@example.com', 'address': '75 Tenges',
            'postal_code': '30401', 'city': 'Nakuru',
        })
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 0)

    def test_order_default_status_is_pending(self):
        self.client.post(reverse('eshop:create_order'), {
            'first_name': 'John', 'last_name': 'Doe',
            'email': 'john@example.com', 'address': '75 Tenges',
            'postal_code': '30401', 'city': 'Nakuru',
        })
        order = Order.objects.first()
        self.assertEqual(order.status, 'PENDING')
        self.assertFalse(order.paid)

    def test_order_detail_page_shows_correct_total(self):
        self.client.post(reverse('eshop:create_order'), {
            'first_name': 'John', 'last_name': 'Doe',
            'email': 'john@example.com', 'address': '75 Tenges',
            'postal_code': '30401', 'city': 'Nakuru',
        })
        order = Order.objects.first()
        response = self.client.get(
            reverse('eshop:order_detail', kwargs={'order_id': order.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2700')


# ── 5. Review Flow ────────────────────────────────────────────────────────────

class ReviewIntegrationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='reviewer', password='StrongPass123!'
        )
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            category=self.category,
            name='iPad Pro',
            slug='ipad-pro',
            price=1620.00,
            available=True,
        )

    def test_logged_in_user_can_add_review(self):
        self.client.login(username='reviewer', password='StrongPass123!')
        response = self.client.post(
            reverse('eshop:add_review', kwargs={'product_slug': self.product.slug}),
            {'rating': 5, 'comment': 'Excellent product!'}
        )
        self.assertEqual(ProductReview.objects.count(), 1)
        review = ProductReview.objects.first()
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.product, self.product)

    def test_unauthenticated_user_cannot_add_review(self):
        response = self.client.post(
            reverse('eshop:add_review', kwargs={'product_slug': self.product.slug}),
            {'rating': 5, 'comment': 'Great!'}
        )
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        self.assertEqual(ProductReview.objects.count(), 0)

    def test_reviews_page_shows_all_reviews(self):
        self.client.login(username='reviewer', password='StrongPass123!')
        ProductReview.objects.create(
            product=self.product, user=self.user, rating=4, comment='Good!'
        )
        response = self.client.get(reverse('eshop:all_reviews'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Good!')


# ── 6. Chatbot API Flow ───────────────────────────────────────────────────────

class ChatbotIntegrationTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        Product.objects.create(
            category=self.category,
            name='iPhone 16 Pro Max',
            slug='iphone-16-pro-max',
            price=1200.00,
            available=True,
        )

    def test_chatbot_responds_to_greeting(self):
        response = self.client.get(reverse('eshop:contact'), {'message': 'hello'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('response', data)
        self.assertIn('Welcome', data['response'])

    def test_chatbot_finds_products_by_name(self):
        response = self.client.get(reverse('eshop:contact'), {'message': 'iphone'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('iPhone 16 Pro Max', data['response'])

    def test_chatbot_returns_delivery_info(self):
        response = self.client.get(reverse('eshop:contact'), {'message': 'delivery time'})
        data = response.json()
        self.assertIn('Delivery', data['response'])

    def test_chatbot_returns_payment_info(self):
        response = self.client.get(reverse('eshop:contact'), {'message': 'payment methods'})
        data = response.json()
        self.assertIn('M-Pesa', data['response'])

    def test_chatbot_handles_empty_message(self):
        response = self.client.get(reverse('eshop:contact'))
        data = response.json()
        self.assertIn('response', data)