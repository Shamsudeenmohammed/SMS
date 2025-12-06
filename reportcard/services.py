# reportcard/services.py
from collections import defaultdict
from django.db.models import Avg
from django.utils import timezone

from finance.models import Invoice
from results.models import ResultRecord
from .models import ReportCard
from accounts.models import Student


# -------------------------
# small helpers
# -------------------------
def ordinal(n):
    """Return ordinal string for a positive integer (1 -> 1st)."""
    try:
        n = int(n)
    except Exception:
        return "-"
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    last = n % 10
    return f"{n}st" if last == 1 else f"{n}nd" if last == 2 else f"{n}rd" if last == 3 else f"{n}th"


# -------------------------
# Calculate subject positions
# -------------------------
def calculate_subject_positions(session, term, classroom, subject):
    """
    For a given session, term, classroom and subject, set ResultRecord.position
    for all matching ResultRecord rows ordered by -total_score.

    `subject` may be a Subject object or an id (primary key).
    """
    qs = ResultRecord.objects.filter(
        session=session,
        term=term,
        classroom=classroom,
        subject=subject
    ).order_by("-total_score")

    position = 1
    last_score = None

    # Use a simple ranking where equal scores share the same position
    for res in qs:
        if last_score is None:
            res.position = 1
        else:
            if res.total_score < last_score:
                position += 1
            res.position = position

        last_score = res.total_score
        # save only if changed (safe)
        res.save(update_fields=["position"])


# -------------------------
# Calculate overall class positions (optimized)
# -------------------------
def calculate_overall_class_positions(session, term, classroom):
    """
    Returns a dict mapping student.id -> position for all students in the classroom.
    Students with no results get total 0 and are included.
    """
    students_in_class = Student.objects.filter(current_class=classroom)

    totals = {}
    for st in students_in_class:
        student_results = ResultRecord.objects.filter(
            student=st,
            session=session,
            term=term
        )
        if student_results.exists():
            totals[st.id] = sum([r.total_score for r in student_results])
        else:
            totals[st.id] = 0

    # Sort by total descending
    sorted_totals = sorted(totals.items(), key=lambda x: x[1], reverse=True)

    positions = {}
    position = 1
    last_score = None

    for student_id, score in sorted_totals:
        if last_score is None:
            positions[student_id] = position
        else:
            if score < last_score:
                position += 1
            positions[student_id] = position

        last_score = score

    return positions


# -------------------------
# Generate per-student report (single)
# -------------------------
def generate_student_report(student, session, term):
    """
    Generate the report data for a single student.
    Returns a dict with keys:
      - student
      - report (ReportCard instance)
      - results (QuerySet)
      - fees (dict)
      - avg_score (float)
      - overall_position (ordinal string or "-")
      - total_students (int)
      - cgpa (None for now)
      - attendance (empty dict placeholder)
      - invoice (Invoice instance or None)
    """
    # Ensure we have a classroom
    classroom = getattr(student, "current_class", None)

    # Create or fetch ReportCard record (store classroom at creation)
    report_obj, _ = ReportCard.objects.get_or_create(
        student=student,
        session=session,
        term=term,
        defaults={"classroom": classroom},
    )

    # Fees / Invoice (may be None)
    invoice = Invoice.objects.filter(student=student, session=session, term=term).first()
    fees_info = {
        "total_due": invoice.total_due if invoice else 0,
        "total_paid": invoice.total_paid if invoice else 0,
        "balance": invoice.balance if invoice else 0,
    }

    # Results (QuerySet)
    results_qs = ResultRecord.objects.filter(
        student=student,
        session=session,
        term=term
    ).order_by("subject__name")

    # Average
    if results_qs.exists():
        avg_score = results_qs.aggregate(Avg("total_score"))["total_score__avg"] or 0
    else:
        avg_score = 0

    # Calculate subject positions (ensure each subject for this student is ranked)
    used_subjects = set()
    for r in results_qs:
        subj = r.subject
        if subj not in used_subjects:
            # subj can be object; calculate_subject_positions accepts either
            calculate_subject_positions(session, term, classroom, subj)
            used_subjects.add(subj)

    # After positions are set on the DB, attach position_display for template
    for r in results_qs:
        r.position_display = ordinal(r.position) if getattr(r, "position", None) else "-"

    # Overall class positions (uses the optimized function)
    overall_positions = calculate_overall_class_positions(session, term, classroom)
    raw_pos = overall_positions.get(student.id)
    overall_position = ordinal(raw_pos) if raw_pos else "-"

    # Persist overall_position on ReportCard if the field exists
    try:
        # Many schemas have a field like 'overall_position' on ReportCard; check and set.
        if hasattr(report_obj, "overall_position"):
            report_obj.overall_position = raw_pos
            report_obj.save(update_fields=["overall_position"])
    except Exception:
        # ignore if the model doesn't support it or save fails
        pass

    return {
        "student": student,
        "report": report_obj,
        "results": results_qs,
        "fees": fees_info,
        "avg_score": round(avg_score, 2) if isinstance(avg_score, (int, float)) else avg_score,
        "overall_position": overall_position,
        "total_students": len(overall_positions),
        "cgpa": None,
        "attendance": {},
        "invoice": invoice,
    }


# -------------------------
# Bulk reports generator
# -------------------------
def generate_bulk_reports(student_ids, session, term):
    """
    student_ids: list of ints OR string "ALL"
    session: Session instance
    term: term string ("1st","2nd","3rd")
    Returns: list of dicts (same structure as generate_student_report output)
    """
    # Grab students
    if student_ids == "ALL":
        students = Student.objects.filter(current_class__isnull=False).order_by("user__last_name")
    else:
        # ensure list of ints
        if isinstance(student_ids, (list, tuple)):
            students = Student.objects.filter(id__in=student_ids).order_by("user__last_name")
        else:
            # if a single id or comma-separated string, normalize
            if isinstance(student_ids, str) and student_ids.isdigit():
                students = Student.objects.filter(id=int(student_ids)).order_by("user__last_name")
            else:
                students = Student.objects.filter(current_class__isnull=False).order_by("user__last_name")

    # Group students by class so we compute overall positions once per class
    classes = defaultdict(list)
    for st in students:
        cls = getattr(st, "current_class", None)
        classes[cls].append(st)

    bulk = []

    for classroom, class_students in classes.items():
        # Pre-compute overall positions for this class
        if classroom is None:
            overall_positions = {}
        else:
            overall_positions = calculate_overall_class_positions(session, term, classroom)

        # For each student in this class:
        for st in class_students:
            # Before generating student report, ensure subject positions for that student's subjects
            # We will let generate_student_report do subject position calculations (idempotent)
            student_report = generate_student_report(st, session, term)

            # Override overall_position and total_students using the precomputed overall_positions
            raw_pos = overall_positions.get(st.id)
            student_report["overall_position"] = ordinal(raw_pos) if raw_pos else "-"
            student_report["total_students"] = len(overall_positions)

            # Also attach invoice and fees are already included
            bulk.append(student_report)

    return bulk
