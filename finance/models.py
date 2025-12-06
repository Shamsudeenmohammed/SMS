from django.db import models

# Create your models here.
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _

# 🔹 Import related models
from accounts.models import CustomUser, Student
from academics.models import Session
import uuid


# ===========================
# 1️⃣ Fee Type
# ===========================
class FeeType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - ₵{self.amount}"


# ===========================
# 2️⃣ Student Fee Record
# ===========================

class StudentFeeRecord(models.Model):
    TERM_CHOICES = [
        ("1st", "1st Term"),
        ("2nd", "2nd Term"),
        ("3rd", "3rd Term"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    fee_type = models.ForeignKey(FeeType, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True)
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_cleared = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "fee_type", "session", "term")
        verbose_name = "Student Fee Record"
        verbose_name_plural = "Student Fee Records"
        ordering = ["-date_created"]

    def save(self, *args, **kwargs):
        self.balance = self.total_amount - self.amount_paid
        self.is_cleared = self.balance <= 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.fee_type} ({self.session} - {self.term})"

# ===========================
# Bulk Fee Assignment (for assigning fees to multiple students based on class/section)

class BulkFeeAssignment(models.Model):
    TERM_CHOICES = [
        ("1st", "1st Term"),
        ("2nd", "2nd Term"),
        ("3rd", "3rd Term"),
    ]

    fee_type = models.ForeignKey(FeeType, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True)
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    target_class = models.ForeignKey('academics.ClassRoom', on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.fee_type} - {self.term} ({self.session})"



# ===========================
# 3️⃣ Payment
# ===========================
class Payment(models.Model):
    PAYMENT_METHODS = [
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
        ("mobile_money", "Mobile Money"),
        ("cheque", "Cheque"),
    ]

    student_fee = models.ForeignKey(StudentFeeRecord, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS)
    reference = models.CharField(max_length=100, unique=True)
    date_paid = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="received_payments")

    reference = models.CharField(max_length=100, unique=True, blank=True)


    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"PAY-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} - ₵{self.amount}"


# ===========================
# 4️⃣ Invoice
# ===========================

class Invoice(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=20, unique=True, editable=False)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True)
    term = models.CharField(max_length=20)
    total_due = models.DecimalField(max_digits=10, decimal_places=2)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_issued = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # 🔹 Auto-generate invoice number only on creation
        if not self.invoice_number:
            current_year = timezone.now().year
            last_invoice = (
                Invoice.objects.filter(invoice_number__startswith=f"INV-{current_year}-")
                .order_by("id")
                .last()
            )

            if last_invoice:
                last_number = int(last_invoice.invoice_number.split("-")[-1])
                new_number = last_number + 1
            else:
                new_number = 1

            self.invoice_number = f"INV-{current_year}-{new_number:04d}"

        # 🔹 Calculate balance and paid status
        self.balance = self.total_due - self.total_paid
        self.is_paid = self.balance <= 0

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} - {self.student.user.get_full_name() if hasattr(self.student, 'user') else str(self.student)}"


# ===========================
# 5️⃣ Finance Summary (for dashboard)
# ===========================
class FinanceSummary(models.Model):
    total_students = models.PositiveIntegerField(default=0)
    total_teachers = models.PositiveIntegerField(default=0)
    total_invoices = models.PositiveIntegerField(default=0)
    total_fees_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_fees_pending = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_fees_unpaid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Finance Summary"

    class Meta:
        verbose_name_plural = "Finance Summary"


