# academics/views.py
from datetime import date, datetime
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from accounts.models import Student, CustomUser
from django.db import transaction
import csv
from django.http import HttpResponse
from .models import ClassRoom, Subject
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Session
from .forms import SessionForm

# ============================================================
# 🚀 MANAGE STUDENT PROMOTIONS / DEMOTIONS

def manage_promotions(request):
    students = Student.objects.select_related("current_class", "user").all()
    classes = ClassRoom.objects.all().order_by("order")

    if request.method == "POST":
        selected_ids = request.POST.getlist("selected_students")
        action = request.POST.get("action")

        for sid in selected_ids:
            student = get_object_or_404(Student, id=sid)
            current_class = student.current_class

            if not current_class:
                continue  # skip if class not assigned

            if action == "promote":
                next_class = ClassRoom.objects.filter(order__gt=current_class.order).order_by("order").first()
                if next_class:
                    student.current_class = next_class
                    student.promoted_to = next_class
                    student.promotion_year = date.today().year
                    student.save()
                else:
                    messages.warning(request, f"{student.user.get_full_name()} is already in the highest class!")

            elif action == "demote":
                prev_class = ClassRoom.objects.filter(order__lt=current_class.order).order_by("-order").first()
                if prev_class:
                    student.current_class = prev_class
                    student.promoted_to = prev_class
                    student.promotion_year = date.today().year
                    student.save()
                else:
                    messages.warning(request, f"{student.user.get_full_name()} is already in the lowest class!")

        if action == "promote":
            messages.success(request, "✅ Selected students promoted successfully!")
        elif action == "demote":
            messages.info(request, "⬇️ Selected students demoted successfully!")

        return redirect("manage_promotions")

    return render(request, "academics/manage_promotions.html", {
        "students": students,
        "classes": classes,
    })



# ============================================================
# 📥 DOWNLOAD STUDENT IMPORT TEMPLATE

def download_student_template(request):
    """Generate a CSV template for student import fully matching import_students."""
    try:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="student_template.csv"'

        writer = csv.writer(response)

        # Header row — MUST match import_students() expected fields
        writer.writerow([
            "username",                      # required
            "full_name",                     # required
            "email (optional)",              # optional
            "current_class",                 # required
            "section",                       # optional
            "guardian_name",                 # optional
            "guardian_contact",              # optional
            "admission_date (YYYY-MM-DD)",   # optional
        ])

        # Example row — matches exactly what import_students accepts
        writer.writerow([
            "john123",
            "John Doe",
            "john@example.com",
            "Grade 1",
            "A",
            "Jane Doe",
            "+233501234567",
            "2025-01-10",
        ])

        return response

    except Exception as e:
        messages.error(request, f"❌ Could not generate CSV template: {str(e)}")
        return redirect("import_students")





# ============================================================
# 📤 IMPORT STUDENTS FROM CSV (Improved + Flexible Date Parsing)
# ============================================================

import csv
from datetime import datetime
from django.utils.timezone import now
from django.db import transaction, IntegrityError
from django.contrib import messages
from django.shortcuts import redirect, render

def import_students(request):
    """Bulk import students from CSV (bug-free and fully aligned with Student model + add_student)."""
    
    if request.method != "POST":
        return render(request, "academics/import_students.html")

    csv_file = request.FILES.get("csv_file")

    if not csv_file:
        messages.error(request, "❌ Please upload a CSV file.")
        return redirect("import_students")

    try:
        # Decode CSV
        decoded_file = csv_file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(decoded_file)

        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for row in reader:

                full_name = (row.get("full_name") or "").strip()
                username = (row.get("username") or "").strip()
                email = (row.get("email") or "").strip()
                class_name = (row.get("current_class") or "").strip()
                section = (row.get("section") or "").strip()
                guardian_name = (row.get("guardian_name") or "").strip()
                guardian_contact = (row.get("guardian_contact") or "").strip()
                admission_date_raw = (row.get("admission_date") or "").strip()

                # ❌ Required fields
                if not full_name or not class_name:
                    skipped_count += 1
                    continue

                # If username missing → auto-generate
                if not username:
                    username = full_name.lower().replace(" ", "")[:10]  # johnDoe → johndoe
                    username += str(now().timestamp()).replace(".", "")[-4:]  # avoid duplicates

                # Parse full name
                parts = full_name.split()
                first_name = parts[0]
                last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

                # Parse admission date safely
                admission_date = None
                if admission_date_raw:
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                        try:
                            admission_date = datetime.strptime(admission_date_raw, fmt).date()
                            break
                        except ValueError:
                            pass

                if not admission_date:
                    admission_date = now().date()

                # Create / Get class
                classroom, _ = ClassRoom.objects.get_or_create(name=class_name)

                # Create the user
                user, created_user = CustomUser.objects.get_or_create(
                    username=username,
                    defaults={
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email if email else None,
                        "role": "student",
                    },
                )

                # Set default password for new users
                if created_user:
                    user.set_password("student123")
                    user.save()

                # Create student profile
                student, created = Student.objects.get_or_create(
                    user=user,
                    defaults={
                        "admission_date": admission_date,
                        "current_class": classroom,
                        "section": section,
                        "guardian_name": guardian_name,
                        "guardian_contact": guardian_contact,
                    },
                )

                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        messages.success(
            request,
            f"✅ {created_count} students imported successfully. "
            f"⛔ {skipped_count} skipped (duplicates or missing required fields). "
            f"Default password set to 'student123' for new accounts."
        )

    except Exception as e:
        messages.error(request, f"❌ Import failed: {str(e)}")
        return redirect("import_students")

    return redirect("import_students")



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ClassRoom
from .forms import ClassRoomForm

def manage_classrooms(request):
    classrooms = ClassRoom.objects.all()

    if request.method == 'POST':
        form = ClassRoomForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'New classroom added successfully!')
            return redirect('manage_classrooms')
    else:
        form = ClassRoomForm()

    return render(request, 'academics/manage_classrooms.html', {
        'form': form,
        'classrooms': classrooms,
    })

def add_classroom(request):
    if request.method == 'POST':
        form = ClassRoomForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Classroom added successfully!")
            return redirect('manage_classrooms')
    else:
        form = ClassRoomForm()

    return render(request, 'academics/add_classroom.html', {
        'form': form
    })



def edit_classroom(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk)
    if request.method == 'POST':
        form = ClassRoomForm(request.POST, instance=classroom)
        if form.is_valid():
            form.save()
            messages.success(request, 'Classroom updated successfully!')
            return redirect('manage_classrooms')
    else:
        form = ClassRoomForm(instance=classroom)
    return render(request, 'academics/edit_classroom.html', {'form': form, 'classroom': classroom})


def delete_classroom(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk)
    classroom.delete()
    messages.warning(request, f'Classroom "{classroom.name}" deleted.')
    return redirect('manage_classrooms')



# ✅ helper: check if user is admin/principal
def is_admin(user):
    return user.is_authenticated and user.role in ["admin", "principal"]

@login_required
@user_passes_test(is_admin)
def subject_list(request):
    subjects = Subject.objects.select_related("classroom", "teacher").order_by("classroom__order", "name")
    return render(request, "academics/subject_list.html", {"subjects": subjects})

@login_required
@user_passes_test(is_admin)
def add_subject(request):
    classes = ClassRoom.objects.all()
    teachers = CustomUser.objects.filter(role="teacher")

    if request.method == "POST":
        name = request.POST.get("name")
        code = request.POST.get("code")
        classroom_id = request.POST.get("classroom")
        teacher_id = request.POST.get("teacher")

        classroom = ClassRoom.objects.get(id=classroom_id)
        teacher = CustomUser.objects.get(id=teacher_id) if teacher_id else None

        Subject.objects.create(name=name, code=code, classroom=classroom, teacher=teacher)
        messages.success(request, "Subject added successfully.")
        return redirect("subject_list")

    return render(request, "academics/subject_form.html", {
        "classes": classes,
        "teachers": teachers,
        "action": "Add Subject"
    })

@login_required
@user_passes_test(is_admin)
def edit_subject(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    classes = ClassRoom.objects.all()
    teachers = CustomUser.objects.filter(role="teacher")

    if request.method == "POST":
        subject.name = request.POST.get("name")
        subject.code = request.POST.get("code")
        subject.classroom_id = request.POST.get("classroom")
        teacher_id = request.POST.get("teacher")
        subject.teacher = CustomUser.objects.get(id=teacher_id) if teacher_id else None
        subject.save()
        messages.success(request, "Subject updated successfully.")
        return redirect("subject_list")

    return render(request, "academics/subject_form.html", {
        "subject": subject,
        "classes": classes,
        "teachers": teachers,
        "action": "Edit Subject"
    })

@login_required
@user_passes_test(is_admin)
def delete_subject(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == "POST":
        subject.delete()
        messages.success(request, "Subject deleted successfully.")
        return redirect("subject_list")
    return render(request, "academics/confirm_delete.html", {"subject": subject})




# ✅ Helper to check if user is admin/principal
# 
@login_required
@user_passes_test(is_admin)
def manage_sessions(request):
    sessions = Session.objects.all()
    return render(request, "academics/manage_sessions.html", {"sessions": sessions})


@login_required
@user_passes_test(is_admin)
def add_session(request):
    if request.method == "POST":
        form = SessionForm(request.POST)
        if form.is_valid():
            # Ensure only one session is_current=True
            if form.cleaned_data["is_current"]:
                Session.objects.update(is_current=False)
            form.save()
            messages.success(request, "✅ Session added successfully!")
            return redirect("manage_sessions")
    else:
        form = SessionForm()
    return render(request, "academics/session_form.html", {"form": form, "title": "Add Session"})


@login_required
@user_passes_test(is_admin)
def edit_session(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == "POST":
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            if form.cleaned_data["is_current"]:
                Session.objects.update(is_current=False)
            form.save()
            messages.success(request, "✅ Session updated successfully!")
            return redirect("manage_sessions")
    else:
        form = SessionForm(instance=session)
    return render(request, "academics/session_form.html", {"form": form, "title": "Edit Session"})


@login_required
@user_passes_test(is_admin)
def delete_session(request, pk):
    session = get_object_or_404(Session, pk=pk)
    session.delete()
    messages.success(request, "🗑️ Session deleted successfully!")
    return redirect("manage_sessions")
