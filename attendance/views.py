from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseServerError
from django.utils.timezone import now
from .forms import AttendanceSessionForm, AttendanceRecordForm
from .models import AttendanceSession, AttendanceRecord
from accounts.models import Teacher, Student
import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from accounts.models import Parent, Student
from .models import AttendanceRecord

logger = logging.getLogger(__name__)

# =========================================
# 1️⃣ Start Attendance Session
# =========================================
@login_required
def start_attendance_session(request):
    try:
        user = request.user

        if not hasattr(user, "teacher_profile"):
            return HttpResponseForbidden("Only teachers can start attendance sessions.")

        teacher = user.teacher_profile

        if request.method == "POST":
            form = AttendanceSessionForm(request.POST, teacher=teacher)
            if form.is_valid():
                # Create or get session for same teacher/subject/classroom/date
                session, created = AttendanceSession.objects.get_or_create(
                    teacher=teacher,
                    subject=form.cleaned_data["subject"],
                    classroom=form.cleaned_data["classroom"],
                    date=form.cleaned_data["date"]
                )
                return redirect("take_attendance", session_id=session.id)
        else:
            form = AttendanceSessionForm(teacher=teacher)

        return render(request, "attendance/start_session.html", {"form": form})

    except Exception as e:
        logger.error(f"Error in start_attendance_session: {e}", exc_info=True)
        return HttpResponseServerError("An unexpected error occurred while starting the session.")


# =========================================
# 2️⃣ Take Attendance
# =========================================
from django.contrib import messages

@login_required
def take_attendance(request, session_id):
    try:
        user = request.user

        if not hasattr(user, "teacher_profile"):
            return HttpResponseForbidden("Only teachers can take attendance.")

        session = get_object_or_404(
            AttendanceSession,
            id=session_id,
            teacher=user.teacher_profile
        )

        form = AttendanceRecordForm(request.POST or None, session=session)

        if request.method == "POST" and form.is_valid():
            for field_name, value in form.cleaned_data.items():
                if field_name.startswith("status_"):
                    student_id = int(field_name.split("_")[1])
                    student = Student.objects.get(id=student_id)

                    AttendanceRecord.objects.update_or_create(
                        session=session,
                        student=student,
                        defaults={"status": value}
                    )

            # ✅ SUCCESS MESSAGE
            messages.success(request, "Attendance submitted successfully ✔️")

            return redirect("teacher_dashboard")

        return render(request, "attendance/take_attendance.html", {
            "form": form,
            "session": session
        })

    except Exception as e:
        logger.error(f"Error in take_attendance: {e}", exc_info=True)
        return HttpResponseServerError(
            "An unexpected error occurred while taking attendance."
        )




@login_required
def parent_attendance(request):
    user = request.user

    if not hasattr(user, "parent_profile"):
        return HttpResponseForbidden("Only parents can access this page.")

    parent = user.parent_profile
    children = parent.children.all()  # Your parent → children relationship

    data = []

    for child in children:
        records = AttendanceRecord.objects.filter(student=child)

        summary = {
            "present": records.filter(status="present").count(),
            "absent": records.filter(status="absent").count(),
            "late": records.filter(status="late").count(),
            "excused": records.filter(status="excused").count(),
        }

        data.append({
            "child": child,
            "summary": summary,
        })

    return render(request, "attendance/parent_attendance.html", {
        "children_data": data
    })


@login_required
def parent_child_attendance_detail(request, child_id):
    user = request.user

    if not hasattr(user, "parent_profile"):
        return HttpResponseForbidden("Only parents can access this page.")

    parent = user.parent_profile
    child = get_object_or_404(Student, id=child_id)

    if child not in parent.children.all():
        return HttpResponseForbidden("This child is not linked to your account.")

    records = AttendanceRecord.objects.filter(student=child).order_by("-session__date")

    return render(request, "attendance/parent_attendance_detail.html", {
        "child": child,
        "records": records,
    })
