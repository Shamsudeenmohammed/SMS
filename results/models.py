from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

# 🔹 Import related models
from accounts.models import Student, CustomUser
from academics.models import Subject, Session, ClassRoom


# =========================================
# 1️⃣ Result Record (Main model for marks)
# =========================================
class ResultRecord(models.Model):
    TERM_CHOICES = [
        ("1st", "1st Term"),
        ("2nd", "2nd Term"),
        ("3rd", "3rd Term"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="results")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="results")
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name="results")
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True)
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    teacher = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'teacher'},
        related_name="marked_results"
    )

    # 🔹 Scores
    test_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(40)])
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(60)])
    total_score = models.DecimalField(max_digits=5, decimal_places=2, editable=False)
    grade = models.CharField(max_length=2, blank=True)
    remark = models.CharField(max_length=100, blank=True)
    position = models.PositiveIntegerField(default=0)


    date_recorded = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('student', 'subject', 'session', 'term')
        ordering = ['student__user__last_name', 'subject__name']
        verbose_name = "Student Result"
        verbose_name_plural = "Student Results"

    def save(self, *args, **kwargs):
        # 🔹 Calculate total
        self.total_score = self.test_score + self.exam_score

        # 🔹 Grade & Remark logic
        if self.total_score >= 80:
            self.grade, self.remark = "A", "Excellent"
        elif self.total_score >= 75:
            self.grade, self.remark = "B+", "Very Good"
        elif self.total_score >= 70:
            self.grade, self.remark = "B", "Good"
        elif self.total_score >= 65:
            self.grade, self.remark = "C+", "Credit"
        elif self.total_score >= 60:
            self.grade, self.remark = "C", "Average"
        elif self.total_score >= 50:
            self.grade, self.remark = "D", "Pass"
        else:
            self.grade, self.remark = "F", "Fail"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.session}, {self.term})"


# =========================================
# 2️⃣ Result Summary per Student (optional)
# =========================================
class ResultSummary(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="result_summaries")
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True)
    term = models.CharField(max_length=10)
    total_subjects = models.PositiveIntegerField(default=0)
    total_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    position = models.PositiveIntegerField(null=True, blank=True)
    date_generated = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'session', 'term')
        verbose_name = "Result Summary"
        verbose_name_plural = "Result Summaries"

    def __str__(self):
        return f"Summary: {self.student} - {self.term} ({self.session})"
