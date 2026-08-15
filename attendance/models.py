from django.db import models
from django.utils.timezone import now
from accounts.models import Teacher, Student
from academics.models import Subject, ClassRoom, Session

# ============================================================
# 1️⃣ AttendanceSession – a single attendance event
# ============================================================
class AttendanceSession(models.Model):
    TERM_CHOICES = [
        ("1st", "1st Term"),
        ("2nd", "2nd Term"),
        ("3rd", "3rd Term"),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="attendance_sessions")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE)
    date = models.DateField(default=now)

    # Auto-attributed to the active academic session (not teacher-selectable)
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True)
    term = models.CharField(max_length=10, choices=TERM_CHOICES, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("teacher", "subject", "classroom", "date")
        ordering = ["-date", "classroom__name", "subject__name"]

    def __str__(self):
        return f"{self.subject.name} | {self.classroom.name} | {self.date}"


# ============================================================
# 2️⃣ AttendanceRecord – each student's attendance
# ============================================================
class AttendanceRecord(models.Model):
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="records")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance_records")

    STATUS_CHOICES = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("late", "Late"),
        ("excused", "Excused"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="present")
    remark = models.CharField(max_length=255, blank=True)
    time_marked = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("session", "student")
        ordering = ["student__user__username"]

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.status}"
