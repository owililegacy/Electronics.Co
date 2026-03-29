from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import Order, ProductReview, Payment, UserProfile


# -------------------------
# Base Styled Form (Reusable)
# -------------------------
class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control w-100',
                'placeholder': field.label.replace('_', ' ').title()
            })


# -------------------------
# User Registration Form
# -------------------------
class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    # Prevent duplicate emails
    def clean_email(self):
        email = self.cleaned_data.get('email')

        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )

        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control w-100',
                'placeholder': (field.label or '').replace('_', ' ').title(),
                'autocomplete': 'off'
            })


# -------------------------
# Order Form
# -------------------------
class OrderForm(StyledModelForm):
    full_name = forms.CharField(
        required=True,
        label='Full Name',
        widget=forms.TextInput(attrs={
            'class': 'form-control w-100',
            'placeholder': 'Full Name',
            'autocomplete': 'off'
        })
    )
    
    class Meta:
        model = Order
        fields = [
            'full_name',
            'email',
            'address',
            'postal_code',
            'city'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-populate full_name from existing first_name and last_name if editing
        if self.instance and self.instance.pk:
            full_name = f"{self.instance.first_name} {self.instance.last_name}".strip()
            self.fields['full_name'].initial = full_name
        
        for field in self.fields.values():
            if field.label != 'Full Name':
                field.widget.attrs.update({
                    'class': 'form-control w-100',
                    'placeholder': field.label.replace('_', ' ').title(),
                    'autocomplete': 'off'
                })
    
    def save(self, commit=True):
        order = super().save(commit=False)
        full_name = self.cleaned_data.get('full_name', '').strip()
        
        # Split full name into first and last name
        if full_name:
            name_parts = full_name.split(' ', 1)
            order.first_name = name_parts[0]
            order.last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        if commit:
            order.save()
        return order


# -------------------------
# Payment Form
# -------------------------
class PaymentForm(StyledModelForm):
    class Meta:
        model = Payment
        fields = [
            'payment_method',
            'account_number'
        ]


# -------------------------
# Product Review Form
# -------------------------
class ReviewForm(StyledModelForm):
    class Meta:
        model = ProductReview
        fields = [
            'rating',
            'comment'
        ]

        widgets = {
            'rating': forms.NumberInput(attrs={
                'min': 1,
                'max': 5
            }),
            'comment': forms.Textarea(attrs={
                'rows': 4
            }),
        }


# -------------------------
# User Profile Forms
# -------------------------
class UserUpdateForm(forms.ModelForm):
    """Form to update User model fields"""
    full_name = forms.CharField(
        required=False,
        label='Full Name',
        widget=forms.TextInput(attrs={
            'class': 'form-control w-100',
            'placeholder': 'Full Name',
            'autocomplete': 'off'
        })
    )
    
    class Meta:
        model = User
        fields = ['email']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the full_name field with the user's current full name
        if self.instance and self.instance.pk:
            full_name = f"{self.instance.first_name} {self.instance.last_name}".strip()
            self.fields['full_name'].initial = full_name
        
        for field in self.fields.values():
            if field.label != 'Full Name':
                field.widget.attrs.update({
                    'class': 'form-control w-100',
                    'placeholder': field.label.replace('_', ' ').title(),
                    'autocomplete': 'off'
                })
    
    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data.get('full_name', '').strip()
        
        # Split full name into first and last name
        if full_name:
            name_parts = full_name.split(' ', 1)
            user.first_name = name_parts[0]
            user.last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    """Form to update UserProfile model fields"""
    class Meta:
        model = UserProfile
        fields = [
            'full_name',
            'bio',
            'profile_picture',
            'phone_number',
            'date_of_birth',
            'address',
            'city',
            'postal_code',
            'country'
        ]
        
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control w-100',
                'placeholder': field.label.replace('_', ' ').title()
            })