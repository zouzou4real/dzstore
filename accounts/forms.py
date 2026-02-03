from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordChangeForm as AuthPasswordChangeForm
from .models import Client, Seller, Feedback, ContactMessage
from .models import Product


def _validate_password_strength(password):
    """Check at least 1 uppercase letter and 1 number. Returns error message or None."""
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    return None


class ClientRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="Password",
        help_text="At least 1 uppercase letter and 1 number required.",
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="Confirm password",
    )

    class Meta:
        model = Client
        fields = ["first_name", "last_name", "username", "email", "age", "password"]

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not password:
            return password
        err = _validate_password_strength(password)
        if err:
            raise ValidationError(err)
        return password

    def clean_age(self):
        age = self.cleaned_data.get("age")
        if age is not None and age < 18:
            raise ValidationError("You must be at least 18 years old to register.")
        return age

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        password2 = cleaned.get("password2")
        if password and password2 and password != password2:
            self.add_error("password2", "The two password fields didn't match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class ClientUpdateForm(forms.ModelForm):
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "Leave blank to keep current"}),
        label="New password",
        help_text="Optional. At least 1 uppercase letter and 1 number.",
    )
    new_password2 = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "Confirm new password"}),
        label="Confirm new password",
    )

    class Meta:
        model = Client
        fields = ["first_name", "last_name", "username", "email", "age"]

    def clean_age(self):
        age = self.cleaned_data.get("age")
        if age is not None and age < 18:
            raise ValidationError("You must be at least 18 years old.")
        return age

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password")
        p2 = cleaned.get("new_password2")
        if p1 or p2:
            if not p1:
                self.add_error("new_password", "Enter a new password to change it.")
            elif not p2:
                self.add_error("new_password2", "Confirm your new password.")
            elif p1 != p2:
                self.add_error("new_password2", "The two password fields didn't match.")
            else:
                err = _validate_password_strength(p1)
                if err:
                    self.add_error("new_password", err)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=commit)
        p = self.cleaned_data.get("new_password")
        if p:
            user.set_password(p)
            if commit:
                user.save(update_fields=["password"])
        return user


class SellerRegistrationForm(forms.ModelForm):
    """
    Seller registration uses the main Client user model plus
    extra fields that will be stored in the linked Seller profile.
    """

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="Password",
        help_text="At least 1 uppercase letter and 1 number required.",
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="Confirm password",
    )
    business_name = forms.CharField(max_length=200, required=False)
    phone_number = forms.CharField(max_length=20, required=False)

    class Meta:
        model = Client
        fields = ["first_name", "last_name", "username", "email", "password"]

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not password:
            return password
        err = _validate_password_strength(password)
        if err:
            raise ValidationError(err)
        return password

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        password2 = cleaned.get("password2")
        if password and password2 and password != password2:
            self.add_error("password2", "The two password fields didn't match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            Seller.objects.create(
                user=user,
                business_name=self.cleaned_data.get("business_name"),
                phone_number=self.cleaned_data.get("phone_number"),
            )
        return user


class SellerUpdateForm(forms.ModelForm):
    business_name = forms.CharField(max_length=200, required=False)
    phone_number = forms.CharField(max_length=20, required=False)

    class Meta:
        model = Client
        fields = ["first_name", "last_name", "username", "email"]

    def __init__(self, *args, **kwargs):
        self.seller_profile = kwargs.pop("seller_profile", None)
        super().__init__(*args, **kwargs)
        if self.seller_profile:
            self.fields["business_name"].initial = self.seller_profile.business_name
            self.fields["phone_number"].initial = self.seller_profile.phone_number

    def save(self, commit=True):
        user = super().save(commit=commit)
        if self.seller_profile:
            self.seller_profile.business_name = self.cleaned_data.get("business_name")
            self.seller_profile.phone_number = self.cleaned_data.get("phone_number")
            if commit:
                self.seller_profile.save()
        return user


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "rows": 2,
                    "maxlength": 500,
                    "placeholder": "Write your feedback...",
                }
            ),
        }


class CustomPasswordChangeForm(AuthPasswordChangeForm):
    """Password change with old-password check and site password rules (1 uppercase + 1 number)."""

    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1")
        if password:
            err = _validate_password_strength(password)
            if err:
                raise ValidationError(err)
        return password


class LandingContactForm(forms.ModelForm):
    """Contact form on the landing page (anonymous submissions)."""

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Your name", "autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com", "autocomplete": "email"}),
            "message": forms.Textarea(attrs={"placeholder": "Your message...", "rows": 4}),
        }


class ProductForm(forms.ModelForm):
    image = forms.URLField(required=False, label="Image URL", max_length=2000)
    class Meta:
        model = Product
        fields = ["name", "description", "image", "quantity", "price", "category"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "image": forms.URLInput(attrs={"maxlength": 2000, "placeholder": "https://..."}),
        }

    def clean_quantity(self):
        q = self.cleaned_data.get("quantity")
        if q is None or q < 0:
            raise ValidationError("Quantity must be zero or a positive integer.")
        return q

    def clean_price(self):
        p = self.cleaned_data.get("price")
        if p is None or p <= 0:
            raise ValidationError("Price must be greater than 0.")
        return p


class FakePaymentForm(forms.Form):
    """Fake payment form for demo only. No real charges."""

    METHOD_CARD = "card"
    METHOD_DZD = "dzd_pay"
    METHOD_CHOICES = [
        (METHOD_CARD, "Credit / Debit card"),
        (METHOD_DZD, "DZD Pay (demo)"),
    ]

    method = forms.ChoiceField(
        choices=METHOD_CHOICES,
        initial=METHOD_CARD,
        widget=forms.RadioSelect,
        label="Payment method",
    )
    cardholder = forms.CharField(
        max_length=120,
        required=True,
        label="Cardholder name",
        widget=forms.TextInput(attrs={"placeholder": "Name on card", "autocomplete": "cc-name"}),
    )
    card_number = forms.CharField(
        max_length=24,
        required=True,
        label="Card number",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4242 4242 4242 4242",
                "autocomplete": "cc-number",
                "inputmode": "numeric",
                "pattern": "[0-9\\s]*",
            }
        ),
    )
    expiry_month = forms.IntegerField(
        min_value=1,
        max_value=12,
        required=True,
        label="Expiry month",
        widget=forms.NumberInput(attrs={"placeholder": "MM", "min": 1, "max": 12}),
    )
    expiry_year = forms.IntegerField(
        min_value=2020,
        max_value=2040,
        required=True,
        label="Expiry year",
        widget=forms.NumberInput(attrs={"placeholder": "YYYY", "min": 2020, "max": 2040}),
    )
    cvv = forms.CharField(
        max_length=8,
        required=True,
        label="CVV",
        widget=forms.TextInput(
            attrs={
                "placeholder": "123",
                "autocomplete": "cc-csc",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
            }
        ),
    )

    def clean_card_number(self):
        val = (self.cleaned_data.get("card_number") or "").replace(" ", "")
        if not val or not val.isdigit():
            raise ValidationError("Enter a valid card number (digits only).")
        if len(val) < 13 or len(val) > 19:
            raise ValidationError("Card number should be 13–19 digits.")
        return val

    def clean_cvv(self):
        val = (self.cleaned_data.get("cvv") or "").strip()
        if not val or not val.isdigit():
            raise ValidationError("Enter a valid CVV (digits only).")
        if len(val) < 3 or len(val) > 4:
            raise ValidationError("CVV should be 3 or 4 digits.")
        return val
