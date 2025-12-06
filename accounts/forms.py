from django import forms
from .models import (
    CustomUser,
    Admin,
    Teacher,
    Student,
    Parent,
    Accountant,
)

class AutoEmailGenerationMixin:
    """
    Ensures that ANY user created/updated will always have a unique email,
    even if none was provided.
    """
    def generate_email(self, base_name):
        base = slugify(base_name) or "user"
        domain = "autogen.local"
        email = f"{base}@{domain}"

        counter = 1
        while User.objects.filter(email__iexact=email).exists():
            email = f"{base}{counter}@{domain}"
            counter += 1

        return email

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        username = (self.cleaned_data.get("username") or "").strip()
        fullname = (self.cleaned_data.get("fullname") or "").strip()

        if email:
            # Ensure uniqueness ONLY if email provided manually
            if User.objects.filter(email__iexact=email).exists():
                raise forms.ValidationError("This email is already in use.")
            return email

        # 🧠 Auto-generate based on username → fullname → fallback
        base = username or fullname or "user"
        return self.generate_email(base)
    
# ============================================================
# 🔹 1️⃣ Base Profile Form (Shared Fields)
# ============================================================
class BaseProfileForm(forms.ModelForm):
    class Meta:
        # All models inheriting BaseProfile have these fields
        fields = ["date_of_birth", "gender", "address", "photo"]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


# ============================================================
# 🔹 2️⃣ Role-Specific Profile Forms
# ============================================================
class AdminProfileForm(BaseProfileForm):
    class Meta(BaseProfileForm.Meta):
        model = Admin
        fields = BaseProfileForm.Meta.fields + ["designation"]
        widgets = {
            **BaseProfileForm.Meta.widgets,
            "designation": forms.TextInput(attrs={"class": "form-control"}),
        }


class TeacherProfileForm(BaseProfileForm):
    class Meta(BaseProfileForm.Meta):
        model = Teacher
        exclude=['date_of_birth','staff_id','user']
        fields = BaseProfileForm.Meta.fields + [
            "staff_id",
            "qualification",
            "department",
            "hire_date",
        ]
        widgets = {
            **BaseProfileForm.Meta.widgets,
            "staff_id": forms.TextInput(attrs={"class": "form-control"}),
            "qualification": forms.TextInput(attrs={"class": "form-control"}),
            "department": forms.TextInput(attrs={"class": "form-control"}),
            "hire_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }


class AccountantProfileForm(BaseProfileForm):
    class Meta(BaseProfileForm.Meta):
        model = Accountant
        fields = BaseProfileForm.Meta.fields + ["employee_id", "hire_date"]
        widgets = {
            **BaseProfileForm.Meta.widgets,
            "employee_id": forms.TextInput(attrs={"class": "form-control"}),
            "hire_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }


from django import forms
from .models import Parent, Student
from django.contrib.auth.models import User  # ✅ To handle username/email linkage

class ParentProfileForm(AutoEmailGenerationMixin, forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    fullname = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    children = forms.ModelMultipleChoiceField(
        queryset=Student.objects.select_related('user').all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'multi-select'})
    )

    class Meta:
        model = Parent
        fields = [
            'username', 'email', 'fullname',
            'gender', 'address', 'photo',
            'occupation', 'relationship', 'children',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("date_of_birth", None)
        self.fields['email'].required = False

    # 🔥 FIX EMAIL VALIDATION ISSUES COMPLETELY
    def clean_email(self):
        email = self.cleaned_data.get("email")
        return email or None   # ✔ allow blank, duplicates, anything


# ============================================================
# 🔹 3️⃣ Student Form (Note: Student is NOT a BaseProfile)
# ============================================================
class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            "student_id",
            "admission_date",
            "date_of_birth",
            "current_class",
            "section",
            "guardian_name",
            "guardian_contact",
            "is_active",
        ]
        widgets = {
            "student_id": forms.HiddenInput(), # Auto-generated, hide from form
            "admission_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "date_of_birth": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "current_class": forms.Select(attrs={"class": "form-control"}),
            "section": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_name": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_contact": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optionally, you can set initial values or modify fields here
        self.fields['email'].required = False


# ============================================================
# 🔹 4️⃣ User Account Info Form (Shared)
# ============================================================
class UserForm(AutoEmailGenerationMixin, forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "username", "email", "phone_number"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False

    def clean_email(self):
        email = self.cleaned_data.get("email")
        return email or None   # ✔ allow blank, invalid format, duplicates





from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from .models import BaseProfile  # adjust based on your actual profile model

class ProfileUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = BaseProfile
        fields = ['photo', 'gender', 'date_of_birth', 'address']  # add others if needed

class UserEmailForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = False

class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter current password'})
    )
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter new password'})
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'})
    )



from django.utils.text import slugify
from django.contrib.auth import get_user_model

User = get_user_model()

