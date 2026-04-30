from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from accounts.models import Student
from academics.models import Session, ClassRoom
from finance.models import Invoice
from results.models import ResultRecord
from .services import calculate_subject_positions, generate_bulk_reports



def calculate_overall_class_positions(session, term, classroom):
    """
    Returns a dictionary {student.id: position} for all students in a class
    based on their total scores in the given session and term.
    """
    from accounts.models import Student

    students_in_class = Student.objects.filter(current_class=classroom)

    # Total score dictionary
    totals = {}

    for student in students_in_class:
        student_results = ResultRecord.objects.filter(
            student=student,
            session=session,
            term=term
        )

        if student_results.exists():
            totals[student.id] = sum(r.total_score for r in student_results)
        else:
            totals[student.id] = 0

    # Sort highest → lowest
    sorted_totals = sorted(totals.items(), key=lambda x: x[1], reverse=True)

    # Assign positions
    positions = {}
    position = 1
    last_score = None

    for student_id, score in sorted_totals:
        if last_score is None or score < last_score:
            positions[student_id] = position
        else:
            # Same position (tie)
            positions[student_id] = position

        last_score = score
        position += 1 if last_score != score else 0

    return positions


# ==========================================================
# 1️⃣ GENERATE REPORT — WRAPPED WITH FULL ERROR HANDLING
# ==========================================================


# 🔹 Ordinal helper
def ordinal(n):
    n = int(n)
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    last = n % 10
    return f"{n}st" if last == 1 else f"{n}nd" if last == 2 else f"{n}rd" if last == 3 else f"{n}th"




@login_required
def generate_report(request, student_id=None, session_id=None, term=None):
    """
    Supports SINGLE REPORT MODE and BULK REPORT MODE
    Only processes active students.
    """

    # ---------------------------------------------------------
    # 🔥 BULK MODE
    # ---------------------------------------------------------
    session_opts = request.session.get("report_options")

    if session_opts:
        try:
            term = session_opts["term"]
            session_obj = Session.objects.get(id=session_opts["session_id"])
            student_ids = session_opts["students"]
            class_id = session_opts["class_id"]

            # Restrict to active students in the selected class
            class_students = Student.objects.filter(
                current_class_id=class_id,
                is_active=True
            ).order_by("user__last_name")

            # Apply specific student selection if not "ALL"
            if student_ids == "ALL":
                final_students = class_students
            else:
                final_students = class_students.filter(id__in=student_ids)

            if not final_students.exists():
                messages.warning(request, "No active students found for this selection.")
                return redirect("select_report_options")

            # Generate bulk data
            bulk_reports = generate_bulk_reports(
                [s.id for s in final_students],
                session_obj,
                term
            )

            # Clear temporary session data
            del request.session["report_options"]

            return render(request, "reportcard/bulk_report_cards.html", {
                "reports": bulk_reports,
                "session": session_obj,
                "term": term,
                "classroom": final_students.first().current_class,
            })

        except Exception as e:
            messages.error(request, f"Bulk report error: {e}")
            return redirect("select_report_options")

    # ---------------------------------------------------------
    # 🔥 SINGLE REPORT MODE
    # ---------------------------------------------------------
    try:
        # Enforce is_active=True even for direct URL access
        student = get_object_or_404(Student, id=student_id, is_active=True)
        session = get_object_or_404(Session, id=session_id)
        classroom = student.current_class

        if classroom is None:
            messages.error(request, "Student does not have an assigned class.")
            return redirect("select_report_options")

        # Results
        results = ResultRecord.objects.filter(
            student=student,
            session=session,
            term=term
        ).order_by("subject__name")

        # Subject positions
        used_subjects = set()
        for r in results:
            if r.subject not in used_subjects:
                calculate_subject_positions(session, term, classroom, r.subject)
                used_subjects.add(r.subject)
            r.position_display = ordinal(r.position) if r.position else "-"

        # Invoice/Financials
        invoice = Invoice.objects.filter(
            student=student,
            session=session,
            term=term
        ).first()

        # Calculation logic
        count = results.count()
        avg_score = round(sum(r.total_score for r in results) / count, 2) if count > 0 else 0

        class_positions = calculate_overall_class_positions(session, term, classroom)
        raw_overall_position = class_positions.get(student.id)
        overall_position = ordinal(raw_overall_position) if raw_overall_position else "-"

        return render(request, "reportcard/report_card.html", {
            "student": student,
            "session": session,
            "term": term,
            "classroom": classroom,
            "results": results,
            "invoice": invoice,
            "avg_score": avg_score,
            "overall_position": overall_position,
            "total_students": len(class_positions),
            "teacher_remarks": "",
            "headmaster_remarks": "",
            "reopening_date": "",
            "cgpa": None,
            "attendance": {},
        })

    except Exception as e:
        messages.error(request, f"Unexpected error: {e}")
        return redirect("select_report_options")


# # ==========================================================
# 2️⃣ SELECT REPORT OPTIONS — SINGLE + BULK VERSION
# ==========================================================

@login_required
def select_report_options(request):
    try:
        classes = ClassRoom.objects.all().order_by("order")
        active_session = Session.objects.filter(is_current=True).first()

        if not active_session:
            messages.error(request, "No active session found.")
            return render(request, "reportcard/select_report_options.html", {
                "classes": classes,
                "students": [],
                "active_session": None,
                "terms": ["1st", "2nd", "3rd"],
            })

        students = []
        selected_class_id = request.GET.get("class_id")

        if selected_class_id:
            # Senior Dev Debug: Check your console/terminal to see if Hafiz appears here
            all_students_in_class = Student.objects.filter(current_class_id=selected_class_id)
            print(f"DEBUG: Total students in class: {all_students_in_class.count()}")
            
            # Explicitly filtering by is_active=True
            students = all_students_in_class.filter(is_active=True).order_by("user__last_name")
            print(f"DEBUG: Active students in class: {students.count()}")

        if request.method == "POST":
            class_id = request.POST.get("class_id")
            term = request.POST.get("term")
            select_all = request.POST.get("select_all")
            selected_students = request.POST.getlist("student_ids")

            if not class_id or not term:
                messages.error(request, "Please select both a class and a term.")
                return redirect("select_report_options")

            # Final server-side safety check: Only pull active IDs
            active_class_students = Student.objects.filter(
                current_class_id=class_id, 
                is_active=True
            )

            if select_all == "on":
                student_ids = "ALL"
            else:
                # Intersect selected IDs with only active IDs to prevent manual URL injection
                allowed_ids = list(active_class_students.values_list('id', flat=True))
                student_ids = [s_id for s_id in selected_students if int(s_id) in allowed_ids]
                
                if not student_ids:
                    messages.error(request, "No valid active students selected.")
                    return redirect("select_report_options")

            request.session["report_options"] = {
                "class_id": class_id,
                "students": student_ids,
                "term": term,
                "session_id": active_session.id,
            }

            return redirect("generate_report", student_id=0, session_id=active_session.id, term=term)

        context = {
            "classes": classes,
            "students": students,
            "active_session": active_session,
            "terms": ["1st", "2nd", "3rd"],
            "selected_class_id": selected_class_id,
        }
        return render(request, "reportcard/select_report_options.html", context)

    except Exception as e:
        messages.error(request, f"Unexpected error: {e}")
        return redirect("dashboard")