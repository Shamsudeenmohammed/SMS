from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from django.utils.timezone import now
from django.db.models.signals import post_save
from django.dispatch import receiver

# ============================================================
# 1️⃣ Custom User Model (Main Entry for All Users)
# ============================================================
class CustomUser(AbstractUser):
    class Roles(models.TextChoices):
        SUPER_ADMIN = "super_admin", _("Super Administrator")
        ADMIN = "admin", _("Administrator / Principal")
        TEACHER = "teacher", _("Teacher")
        STUDENT = "student", _("Student")
        ACCOUNTANT = "accountant", _("Accountant")
        PARENT = "parent", _("Parent / Guardian")

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=False, blank=True, null=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.STUDENT)
    phone_number = models.CharField(
        max_length=15,
        validators=[RegexValidator(r"^\+?\d{9,15}$", "Enter a valid phone number.")],
        blank=True,
        null=True,
    )
    is_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "username"

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def profile_photo(self):
        """
        Dynamically fetches the photo URL from the associated profile.
        If no profile or photo exists, returns the static default path.
        """
        # Dictionary mapping roles to their related profile names
        profile_map = {
            self.Roles.ADMIN: 'admin_profile',
            self.Roles.TEACHER: 'teacher_profile',
            self.Roles.ACCOUNTANT: 'accountant_profile',
            self.Roles.PARENT: 'parent_profile',
            self.Roles.STUDENT: 'student_profile',
        }

        try:
            # Get the correct profile attribute based on user role
            profile_attr = profile_map.get(self.role)
            if profile_attr:
                profile = getattr(self, profile_attr, None)
                # Check if profile exists and has a photo with a valid file
                if profile and profile.photo and hasattr(profile.photo, 'url'):
                    return profile.photo.url
        except Exception:
            pass

        # Return the URL via settings.MEDIA_URL + default path
        from django.conf import settings
        return f"{settings.MEDIA_URL}profiles/default.png"


# ============================================================
# 2️⃣ Base Profile (Shared Info for All User Types)
# ============================================================
class BaseProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="%(class)s_profile")
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=[("Male", "Male"), ("Female", "Female")],
        blank=True,
    )
    address = models.CharField(max_length=255, blank=True)
    photo = models.ImageField(upload_to="profiles/", default="profiles/default.png")

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"


# ============================================================
# 3️⃣ Role-Specific Profiles
# ============================================================
class Admin(BaseProfile):
    designation = models.CharField(max_length=100, default="Principal")


class Teacher(BaseProfile):
    staff_id = models.CharField(max_length=30, unique=True, blank=True)  # allow blank
    qualification = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    hire_date = models.DateField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.staff_id:
            # Get initials from full name
            full_name = self.user.get_full_name() or self.user.username
            initials = "".join([name[0].upper() for name in full_name.split() if name])

            year = now().year
            # Find last staff_id with same year & initials
            last_teacher = Teacher.objects.filter(staff_id__startswith=f"T-{year}-{initials}").order_by('staff_id').last()
            if last_teacher and last_teacher.staff_id:
                last_number = int(last_teacher.staff_id.split('-')[-1])
                new_number = last_number + 1
            else:
                new_number = 1

            self.staff_id = f"T-{year}-{initials}-{new_number:04d}"  # e.g., T-2025-JD-0001
        super().save(*args, **kwargs)




class Accountant(BaseProfile):
    employee_id = models.CharField(max_length=20, unique=True)
    hire_date = models.DateField(blank=True, null=True)


class Parent(BaseProfile):
    date_of_birth = None  # Disable inherited field

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Forcefully remove inherited date_of_birth from model metadata
        if 'date_of_birth' in cls._meta.fields_map:
            del cls._meta.fields_map['date_of_birth']

    occupation = models.CharField(max_length=100, blank=True)

    relationship = models.CharField(
        max_length=20,
        choices=[
            ("Father", "Father"),
            ("Mother", "Mother"),
            ("Guardian", "Guardian"),
        ],
        default="Guardian",
    )

    # Parent can have multiple children
    children = models.ManyToManyField(
        'accounts.Student',
        related_name='parents',
        blank=True
    )

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.relationship})"



# ============================================================
# 3️⃣ Student Profile with Auto-generated Student ID
from django.db import models
from django.utils.timezone import now
from django.db.models import Max

class Student(BaseProfile):
    user = models.OneToOneField('accounts.CustomUser', on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True, blank=True)
    admission_date = models.DateField(blank=True, null=True)
    current_class = models.ForeignKey('academics.ClassRoom', on_delete=models.SET_NULL, null=True, blank=True)
    section = models.CharField(max_length=50, blank=True)
    guardian_name = models.CharField(max_length=100, blank=True)
    guardian_contact = models.CharField(max_length=15, blank=True)
    is_active = models.BooleanField(default=True)
    promotion_year = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"

    def promote(self, next_class):
        current_year = now().year
        if self.promotion_year == current_year:
            return False
        self.current_class = next_class
        self.promotion_year = current_year
        self.save()
        return True

    def save(self, *args, **kwargs):
        # 🔹 Auto-generate student_id only if not already set
        if not self.student_id:
            admission_year = self.admission_date.year if self.admission_date else now().year
            prefix = str(admission_year)
            
            # 🔹 Get the latest student_id for this year
            last_student = Student.objects.filter(student_id__startswith=prefix).aggregate(
                Max('student_id')
            )['student_id__max']
            
            if last_student:
                # Increment the numeric part
                last_number = int(last_student[-4:])  # last 4 digits
                new_number = last_number + 1
            else:
                new_number = 1  # start from 0001 for new year

            # 🔹 Build 8-digit ID (e.g., 20250001)
            self.student_id = f"{prefix}{new_number:04d}"
        
        super().save(*args, **kwargs)


# ============================================================
# 4️⃣ Auto-create profile after user registration
# ============================================================
@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == CustomUser.Roles.ADMIN:
            Admin.objects.create(user=instance)
        elif instance.role == CustomUser.Roles.TEACHER:
            Teacher.objects.create(user=instance)
        elif instance.role == CustomUser.Roles.ACCOUNTANT:
            Accountant.objects.create(user=instance, employee_id=f"A-{instance.id}")
        elif instance.role == CustomUser.Roles.PARENT:
            Parent.objects.create(user=instance)

