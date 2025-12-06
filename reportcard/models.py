# reportcard/models.py

from django.db import models
from django.utils import timezone
from accounts.models import Student, CustomUser
from academics.models import Session, ClassRoom

class ReportCard(models.Model):
    TERM_CHOICES = [
        ("1st", "1st Term"),
        ("2nd", "2nd Term"),
        ("3rd", "3rd Term"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="report_cards")
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True)
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    classroom = models.ForeignKey(ClassRoom, on_delete=models.SET_NULL, null=True)

    # auto calculated later
    overall_average = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    position_in_class = models.PositiveIntegerField(default=0)

    # filled by teacher on click
    teacher_remark = models.TextField(blank=True)
    teacher_signature = models.ImageField(upload_to="signatures/", blank=True, null=True)

    # filled manually after print
    headmaster_remark = models.TextField(blank=True)
    reopening_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "session", "term")

    def __str__(self):
        return f"{self.student} | {self.session} | {self.term}"
