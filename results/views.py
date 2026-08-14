from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse

from academics.models import Subject, Session, Enrollment
from accounts.models import Student
from .models import ResultRecord
from .forms import ResultEntryForm
import csv
import io




# View for teachers to mark results

@login_required
def mark_results(request):
    """Allow teachers to mark results only for their assigned subjects, while preserving historical results."""
    teacher = request.user

    if teacher.role != "teacher":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("dashboard")

    # 🔹 Subjects assigned to this teacher
    subjects = Subject.objects.filter(teacher=teacher).select_related("classroom")
    sessions = Session.objects.filter(is_current=True)

    # 🔹 Filters from GET
    session_id = request.GET.get("session")
    subject_id = request.GET.get("subject")
    term = request.GET.get("term")

    selected_subject = None
    combined = []  # student-result pairs for template

    if subject_id and session_id and term:
        selected_subject = get_object_or_404(Subject, id=subject_id, teacher=teacher)
        session = get_object_or_404(Session, id=session_id)
        classroom = selected_subject.classroom

        # 🔹 Current session students (auto detect class)
        students = Student.objects.filter(current_class=classroom, is_active=True).select_related("user")

        # 🔹 Ensure each student is enrolled in the subject
        for student in students:
            Enrollment.objects.get_or_create(student=student, subject=selected_subject)

        # 🔹 Ensure each student has a result record for this session & term
        results_data = []
        for student in students:
            result, _ = ResultRecord.objects.get_or_create(
                student=student,
                subject=selected_subject,
                classroom=classroom,
                session=session,
                term=term,
                defaults={"teacher": teacher, "test_score": 0, "exam_score": 0},
            )
            results_data.append(result)

        combined = zip(students, results_data)

        # 🔹 Handle POST (bulk saving results)
        if request.method == "POST":
            try:
                with transaction.atomic():
                    for student, record in zip(students, results_data):
                        test_score = request.POST.get(f"test_{student.id}", "0")
                        exam_score = request.POST.get(f"exam_{student.id}", "0")

                        record.test_score = float(test_score or 0)
                        record.exam_score = float(exam_score or 0)
                        record.teacher = teacher
                        record.save()

                messages.success(request, "✅ Results saved successfully!")
                return redirect("mark_results")
            except Exception as e:
                messages.error(request, f"❌ Error saving results: {e}")

    # 🔹 Historical results for this student (all sessions)
    historical_results = {}
    if selected_subject:
        for student in students:
            historical_results[student.id] = ResultRecord.objects.filter(student=student).exclude(session_id=session_id)

    return render(request, "results/mark_results.html", {
        "subjects": subjects,
        "sessions": sessions,
        "combined": combined,
        "selected_subject": selected_subject,
        "selected_session": session_id,
        "selected_term": term,
        "historical_results": historical_results,
    })


# View for uploading results via CSV
@login_required
def upload_results(request):
    """Allow teachers to upload a CSV of results for a specific subject/session/term."""
    teacher = request.user

    if teacher.role != "teacher":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("dashboard")

    subjects = Subject.objects.filter(teacher=teacher).select_related("classroom")
    sessions = Session.objects.all().order_by("-start_date")

    if request.method == "POST":
        session_id = request.POST.get("session")
        term = request.POST.get("term")
        subject_id = request.POST.get("subject")
        file = request.FILES.get("file")

        if not (session_id and term and subject_id and file):
            messages.error(request, "Please select session, term, subject and upload a file.")
            return redirect("mark_results")

        session = get_object_or_404(Session, id=session_id)
        subject = get_object_or_404(Subject, id=subject_id, teacher=teacher)
        classroom = subject.classroom

        try:
            decoded_file = file.read().decode("utf-8").splitlines()
            reader = csv.DictReader(decoded_file)

            with transaction.atomic():
                for row in reader:
                    student_id = row.get("student_id")
                    test_score = float(row.get("test_score", 0))
                    exam_score = float(row.get("exam_score", 0))

                    # 🔹 Detect student (active or previously enrolled)
                    student = Student.objects.get(id=student_id, is_active=True)

                    # 🔹 Auto-create or update result for the session/term only
                    result, created = ResultRecord.objects.get_or_create(
                        student=student,
                        subject=subject,
                        session=session,
                        term=term,
                        defaults={
                            "classroom": student.current_class,
                            "teacher": teacher,
                            "test_score": test_score,
                            "exam_score": exam_score,
                        }
                    )

                    if not created:
                        result.test_score = test_score
                        result.exam_score = exam_score
                        result.teacher = teacher
                        result.save()

            messages.success(request, "✅ Results uploaded successfully!")
            return redirect("mark_results")

        except Student.DoesNotExist:
            messages.error(request, "❌ One or more students in the CSV do not exist or are inactive.")
        except Exception as e:
            messages.error(request, f"❌ Error processing file: {e}")

    return redirect("mark_results")


@login_required
def download_results_template(request):
    """Generate CSV template for teachers to fill results."""
    teacher = request.user

    if teacher.role != "teacher":
        messages.error(request, "You are not authorized to access this page.")
        return redirect("dashboard")

    session_id = request.GET.get("session")
    subject_id = request.GET.get("subject")

    if not (session_id and subject_id):
        messages.error(request, "Please select both session and subject to download template.")
        return redirect("mark_results")

    session = get_object_or_404(Session, id=session_id)
    subject = get_object_or_404(Subject, id=subject_id, teacher=teacher)
    classroom = subject.classroom

    # Students in the class
    students = Student.objects.filter(current_class=classroom, is_active=True).select_related("user")

    # CSV response
    response = HttpResponse(content_type="text/csv")
    filename = f"results_template_{subject.name}_{session.name}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["student_id", "student_name", "test_score", "exam_score"])
    for student in students:
        writer.writerow([student.id, student.user.get_full_name(), 0, 0])

    return response


# View for students to see their results
@login_required
def view_my_results(request):
    student = request.user.student
    sessions = Session.objects.all()
    selected_session_id = request.GET.get("session")
    selected_term = request.GET.get("term")

    results = []
    total_score = average = 0

    if selected_session_id and selected_term:
        results = ResultRecord.objects.filter(
            student=student,
            session_id=selected_session_id,
            term=selected_term,
            test_score__isnull=False,
            exam_score__isnull=False
        ).exclude(test_score=0, exam_score=0)

        if results.exists():
            total_score = sum(r.total_score for r in results)
            average = round(total_score / results.count(), 2)

    context = {
        "sessions": sessions,
        "results": results,
        "selected_session_id": selected_session_id,
        "selected_term": selected_term,
        "total_score": total_score,
        "average": average,
    }
    return render(request, "results/view_my_results.html", context)




@login_required
def download_result(request):
    from xhtml2pdf import pisa
    from collections import defaultdict
    from django.utils.text import slugify

    student = request.user.student
    selected_session_id = request.GET.get("session")

    # Get sessions
    if selected_session_id:
        sessions = Session.objects.filter(id=selected_session_id)
    else:
        sessions = Session.objects.all().order_by("start_date")  # oldest → newest

    # Define term ordering
    term_order = {"1st": 1, "2nd": 2, "3rd": 3}

    # Prepare flattened results for template
    results_data = []

    for session in sessions:
        session_results = ResultRecord.objects.filter(
            student=student,
            session=session,
            test_score__isnull=False,
            exam_score__isnull=False
        ).exclude(test_score=0, exam_score=0)

        if session_results.exists():
            # Session totals
            session_total = sum(r.total_score for r in session_results)
            session_average = round(session_total / session_results.count(), 2)

            # Group results by term
            term_counter = defaultdict(list)
            for r in session_results:
                term_counter[r.term].append(r)

            term_list = []
            for term_name, results in term_counter.items():
                term_total = sum(r.total_score for r in results)
                term_average = round(term_total / len(results), 2)
                term_list.append({
                    "term_name": term_name,
                    "results": results,
                    "total": term_total,
                    "average": term_average
                })

            # Sort terms
            term_list = sorted(term_list, key=lambda t: term_order.get(t["term_name"], 99))

            results_data.append({
                "session": session,
                "terms": term_list,
                "session_total": session_total,
                "session_average": session_average
            })

    context = {
        "student": student,
        "results_data": results_data
    }

    # PDF generation
    template_path = 'results/result_pdf.html'
    response = HttpResponse(content_type='application/pdf')

    # 🔥 Create clean PDF filename: username → full name → id
    safe_name = slugify(
        student.user.username
        or student.user.get_username()
        or str(student.id)
    )

    if selected_session_id:
        filename = f"{safe_name}_session_result.pdf"
    else:
        filename = f"{safe_name}_full_result.pdf"

    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    html = render(request, template_path, context).content.decode('utf-8')
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)

    return response
