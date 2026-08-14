from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Admin, Teacher, Student, Accountant, Parent

# Customize the admin site headers and titles
admin.site.site_header = "School Management System"
admin.site.site_title = "School Management System Admin Portal"
admin.site.index_title = "Welcome to the School Management System Admin Portal"

# 
# 1️⃣ Custom User Admin
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_active", "is_staff")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email")
    ordering = ("username",)

    # Simplify form fields
    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "phone_number")}),
        ("Role & Permissions", {"fields": ("role", "is_staff", "is_superuser", "is_active")}),
        ("Verification", {"fields": ("is_verified",)}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username",
                "email",
                "password1",
                "password2",
                "role",
                "is_active",
            ),
        }),
    )


# 
# 2️⃣ Shared Inline Mixins (for related profiles)
# 
class BaseProfileAdmin(admin.ModelAdmin):
    list_per_page = 20
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user",)
    save_on_top = True


# 
# 3️⃣ Role-Specific Admins
# 
@admin.register(Admin)
class AdminAdmin(BaseProfileAdmin):
    list_display = ("user", "designation", "gender", "address")
    list_filter = ("designation",)


@admin.register(Teacher)
class TeacherAdmin(BaseProfileAdmin):
    list_display = ("user", "staff_id", "department", "qualification")
    list_filter = ("department", "qualification")


from django.contrib import admin
from accounts.models import Student

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("student_id", "user", "current_class", "section", "promotion_year", "is_active")
    search_fields = ("student_id", "user__first_name", "user__last_name", "current_class", "section")
    list_filter = ("current_class", "section")

    actions = ["promote_students", "demote_students"]

    def promote_students(self, request, queryset):
        for student in queryset:
            next_class = f"{student.current_class} + 1"  # You can customize promotion naming logic
            student.promote(next_class)
        self.message_user(request, f"{queryset.count()} students promoted successfully.")
    promote_students.short_description = "🚀 Promote selected students"

    def demote_students(self, request, queryset):
        for student in queryset:
            prev_class = f"{student.current_class} - 1"
            student.demote(prev_class)
        self.message_user(request, f"{queryset.count()} students demoted successfully.")
    demote_students.short_description = "📉 Demote selected students"


@admin.register(Accountant)
class AccountantAdmin(BaseProfileAdmin):
    list_display = ("user", "employee_id", "hire_date")
    list_filter = ("hire_date",)


@admin.register(Parent)
class ParentAdmin(BaseProfileAdmin):
    list_display = ("user", "occupation", "relationship")
    filter_horizontal = ("children",)
    list_filter = ("relationship",)



