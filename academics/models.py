from django.db import models
from django.utils import timezone
from accounts.models import CustomUser,Student


# ===============================
# 🔹 ACADEMIC SESSION
# ===============================
class Session(models.Model):
    name = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']

from django.db import transaction

def save(self, *args, **kwargs):
    if self.is_current:
        with transaction.atomic():
            # Unmark all others, but keep it efficient
            Session.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
    super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ===============================
# 🔹 CLASSROOM / LEVEL

# academics/models.py
class ClassRoom(models.Model):
    name = models.CharField(max_length=50, unique=True)
    order = models.PositiveIntegerField(default=0, unique=True)  # determines class order
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name




# ===============================
# 🔹 SUBJECT
# ===============================

class Subject(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=20, unique=True)
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name="subjects")
    teacher = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'teacher'}
    )

    def __str__(self):
        return f"{self.name} - {self.classroom.name}"




# ===============================
# 🔹 ENROLLMENT (LINK STUDENT & SUBJECT)
# ===============================
class Enrollment(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="enrollments"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="enrollments"
    )
    date_enrolled = models.DateField(default=timezone.now)

    class Meta:
        unique_together = ("student", "subject")

    def __str__(self):
        return f"{self.student} → {self.subject}"


# ===============================
# 🔹 GRADES / RESULTS
# ===============================
TERM_CHOICES = [
    ("1st Term", "1st Term"),
    ("2nd Term", "2nd Term"),
    ("3rd Term", "3rd Term"),
]
