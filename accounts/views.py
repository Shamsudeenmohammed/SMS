# ==========================================
# ✅ CLEAN & OPTIMIZED ACCOUNTS VIEWS
# ==========================================

from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum, Q, Avg
from django.utils import timezone

from .models import CustomUser, Student, Teacher, Parent
from finance.models import Invoice, Payment, FinanceSummary, StudentFeeRecord
from academics.models import Session, Subject
from results.models import ResultRecord, ResultSummary
from django.urls import resolve
from decimal import Decimal
from .forms import TeacherProfileForm, UserForm, StudentForm, ParentProfileForm



User = get_user_model()




from django.core.management import call_command
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required


import json
from django.http import HttpResponse
from django.core.serializers import serialize
from django.contrib.auth.decorators import user_passes_test

@user_passes_test(lambda u: u.is_superuser)
def export_data(request):
    try:
        data = serialize(
            "json",
            [],
            use_natural_primary_keys=True,
            use_natural_foreign_keys=True,
            indent=4
        )

        from django.apps import apps
        all_models = apps.get_models()

        all_objects = []
        for model in all_models:
            all_objects.extend(model.objects.all())

        data = serialize(
            "json",
            all_objects,
            use_natural_primary_keys=True,
            use_natural_foreign_keys=True,
            indent=4,
            ensure_ascii=False  # Important: prevents encoding errors
        )

        response = HttpResponse(data, content_type="application/json; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="db_backup.json"'
        return response

    except Exception as e:
        return HttpResponse(f"<h3 style='color:red;'>❌ Error: {e}</h3>")



# ==========================================
# 1️⃣ AUTHENTICATION
# ==========================================
def custom_login(request):
    """Universal login for all roles."""
    if request.user.is_authenticated:
        return redirect_user_based_on_role(request.user)

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect_user_based_on_role(user)
        messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html")



def redirect_user_based_on_role(user, request=None):
    """Redirect authenticated user to correct dashboard safely."""
    if not user.is_authenticated:
        return redirect("custom_login")

    if user.is_superuser:
        return redirect("/getout/")

    role = getattr(user, "role", "").lower()
    dashboard_map = {
        "admin": "admin_dashboard",
        "teacher": "teacher_dashboard",
        "student": "student_dashboard",
        "accountant": "accountant_dashboard",
        "parent": "parent_dashboard",
    }

    target = dashboard_map.get(role)

    # Prevent infinite redirect loop if already on same dashboard
    if request:
        current_view = resolve(request.path_info).url_name
        if current_view == target:
            return None  # don’t redirect again

    return redirect(target or "custom_login")



def custom_logout(request):
    logout(request)
    return redirect("custom_login")


# ==========================================
# 2️⃣ DASHBOARD REDIRECT
# ==========================================
@login_required
def dashboard(request):
    """Main fallback dashboard (for unknown roles)."""
    role = getattr(request.user, "role", "").lower()

    if role == "admin":
        return redirect("admin_dashboard")
    elif role == "teacher":
        return redirect("teacher_dashboard")
    elif role == "student":
        return redirect("student_dashboard")
    elif role == "accountant":
        return redirect("accountant_dashboard")
    elif role == "parent":
        return redirect("parent_dashboard")

    messages.warning(request, "No dashboard found for your role.")
    return render(request, "accounts/dashboard.html")  # simple neutral page




# ==========================================
# 3️⃣ PROFILE
# ==========================================
@login_required
def profile(request):
    user = request.user
    role = getattr(user, "role", "").capitalize()
    profile_data = None

    model_map = {
        "Student": Student,
        "Teacher": Teacher, 
        "Parent": Parent,
        "Admin":Admin,
        "Accountant":Accountant
    }
    
    if role in model_map:
        try:
            profile_data = model_map[role].objects.get(user=user)
        except ObjectDoesNotExist:
            pass

    return render(request, "accounts/profile.html", {
        "user": user,
        "profile_data": profile_data,
        "role": role,
    })


# ==========================================
# 4️⃣ DASHBOARDS
# ==========================================
@login_required
def admin_dashboard(request):
    total_students = Student.objects.count()
    total_teachers = Teacher.objects.count()
    total_invoices = Invoice.objects.count()

    invoice_stats = Invoice.objects.aggregate(
        total_paid=Sum("total_paid"),
        total_due=Sum("total_due"),
    )

    total_paid = invoice_stats["total_paid"] or Decimal("0")
    total_due = invoice_stats["total_due"] or Decimal("0")
    total_balance = total_due - total_paid


    fully_paid = Invoice.objects.filter(is_paid=True).count()
    partially_paid = Invoice.objects.filter(balance__gt=0, total_paid__gt=0).count()
    unpaid = Invoice.objects.filter(total_paid=0).count()
    total_due = float(invoice_stats['total_due'] or 0)

    pending_total = Invoice.objects.filter(
        balance__gt=0, total_paid__gt=0
    ).aggregate(total=Sum("balance"))["total"] or 0

    # Chart Data (Last 12 Months)
    today = timezone.now().date()
    months, revenues = [], []
    
    for i in range(11, -1, -1):
        month_start = today.replace(day=1) - timedelta(days=30 * i)
        month_end = (month_start + timedelta(days=31)).replace(day=1)
        label = month_start.strftime("%b %Y")

        total = Payment.objects.filter(
            date_paid__gte=month_start, date_paid__lt=month_end
        ).aggregate(total=Sum("amount"))["total"] or 0

        months.append(label)
        revenues.append(float(total))

    # Sync Finance Summary
    FinanceSummary.objects.update_or_create(
        id=1,
        defaults={
            'total_students': total_students,
            'total_invoices': total_invoices,
            'total_fees_paid': total_paid,
            'total_fees_pending': pending_total,
            'total_fees_unpaid': total_balance,
        }
    )

    return render(request, "accounts/admin_dashboard.html", {
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_invoices": total_invoices,
        "total_fees_due": total_due,
        "total_fees_paid": total_paid,
        "pending_fees": pending_total,
        "unpaid_fees": total_balance,
        "fully_paid": fully_paid,
        "partially_paid": partially_paid,
        "unpaid": unpaid,
        "monthly_labels": months,
        "monthly_revenue": revenues,
    })





# ✅ Manage list
@login_required
def manage_parents(request):
    query = request.GET.get('q', '')
    parents = Parent.objects.all()

    if query:
        parents = parents.filter(
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(occupation__icontains=query)
        ).distinct()

    return render(request, 'accounts/manage_parents.html', {'parents': parents})


# ✅ Add parent
# views.py
import secrets
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from django.utils.text import slugify
from django.contrib.auth.decorators import login_required

from .forms import ParentProfileForm  # your form
from .models import Parent, Student  # adjust to your actual model paths

logger = logging.getLogger(__name__)
User = get_user_model()


@login_required
def add_parent(request):
    try:
        if request.method == "POST":
            form = ParentProfileForm(request.POST, request.FILES)

            if form.is_valid():
                try:
                    with transaction.atomic():
                        # use safe defaults so .strip() never runs on None
                        username_input = (form.cleaned_data.get("username") or "").strip()
                        email_raw = form.cleaned_data.get("email")
                        email = (email_raw or "").strip() or None

                        full_name = (
                            (form.cleaned_data.get("fullname") or "")
                            or (form.cleaned_data.get("name") or "")
                            or "Parent User"
                        )
                        full_name = full_name.strip()

                        # Split full name safely
                        parts = full_name.split()
                        first_name = parts[0] if parts else ""
                        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

                        # Build unique username (fallback to full_name if username_input blank)
                        base = slugify(username_input) if username_input else slugify(full_name) or "parent"
                        username = base
                        counter = 1
                        while User.objects.filter(username=username).exists():
                            username = f"{base}{counter}"
                            counter += 1

                        # Email uniqueness only when provided
                        if email and User.objects.filter(email__iexact=email).exists():
                            messages.error(request, "❌ This email is already linked to another user.")
                            return render(request, "accounts/parent_form.html", {
                                "form": form,
                                "title": "Add Parent"
                            })

                        # Create temporary password
                        temp_password = secrets.token_urlsafe(8)

                        # Create User Account
                        user = User.objects.create_user(
                            username=username,
                            email=email,
                            password=temp_password,
                            first_name=first_name,
                            last_name=last_name,
                        )

                        # Assign role if model has `role`
                        if hasattr(user, "role"):
                            try:
                                user.role = "parent"
                                user.save(update_fields=["role"])
                            except Exception:
                                # non-fatal: log and continue
                                logger.exception("Failed to set user.role for new parent")

                        # Create Parent Profile
                        parent_profile = form.save(commit=False)
                        parent_profile.user = user
                        parent_profile.save()
                        form.save_m2m()

                        # Attach children / students (if present)
                        children_selected = form.cleaned_data.get("children") or form.cleaned_data.get("students")
                        if children_selected:
                            # ensure the related name exists
                            if hasattr(parent_profile, "children"):
                                parent_profile.children.set(children_selected)
                            elif hasattr(parent_profile, "students"):
                                parent_profile.students.set(children_selected)

                        messages.success(
                            request,
                            f"Parent '{full_name}' added successfully. Username: {username} | Temporary Password: {temp_password}"
                        )
                        return redirect("manage_parents")

                except Exception as inner_exc:
                    logger.exception("Error while saving parent")
                    messages.error(request, f"⚠️ Saving failed: {inner_exc}")

            else:
                messages.error(request, "⚠️ Please correct the highlighted errors.")

        else:
            form = ParentProfileForm()

        return render(request, "accounts/parent_form.html", {
            "form": form,
            "title": "Add Parent"
        })

    except Exception as exc:
        logger.exception("UNEXPECTED ERROR in add_parent")
        messages.error(request, f"🔥 Unexpected error: {exc}")
        return render(request, "accounts/parent_form.html", {
            "form": ParentProfileForm(),
            "title": "Add Parent",
            "error_message": str(exc),
        })


from django.db import IntegrityError, transaction
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Parent, CustomUser
from .forms import ParentProfileForm

@login_required
@transaction.atomic
def edit_parent(request, pk):
    parent = get_object_or_404(Parent, pk=pk)
    user = parent.user

    try:
        if request.method == "POST":
            form = ParentProfileForm(request.POST, request.FILES, instance=parent)

            if form.is_valid():

                # Safe get with default fallback and strip
                username = (form.cleaned_data.get("username") or user.username).strip()
                email = (form.cleaned_data.get("email") or "").strip() or None
                full_name = (form.cleaned_data.get(
                    "fullname") or f"{user.first_name} {user.last_name}").strip()

                # --- USERNAME CHECK ---
                if CustomUser.objects.filter(username=username).exclude(pk=user.pk).exists():
                    messages.error(request, "❌ Username already exists.")
                    return render(request, "accounts/parent_form.html", {
                        "form": form,
                        "title": "Edit Parent",
                        "editing": True,
                    })

                # --- EMAIL CHECK ---
                if email and CustomUser.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    messages.error(request, "❌ Email already exists.")
                    return render(request, "accounts/parent_form.html", {
                        "form": form,
                        "title": "Edit Parent",
                        "editing": True,
                    })

                # --- UPDATE USER ---
                parts = full_name.split()
                user.first_name = parts[0] if parts else ""
                user.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                user.username = username
                user.email = email
                user.save()

                # --- UPDATE PARENT PROFILE ---
                parent_obj = form.save(commit=False)
                parent_obj.user = user
                parent_obj.save()
                form.save_m2m()

                # --- OPTIONAL PASSWORD UPDATE ---
                new_password = request.POST.get("new_password")
                confirm_password = request.POST.get("confirm_password")
                if new_password:
                    if new_password == confirm_password or confirm_password is None:
                        user.set_password(new_password)
                        user.save()
                        messages.success(request, "🔑 Parent updated and password reset.")
                    else:
                        messages.error(request, "❌ Passwords do not match.")
                        return render(request, "accounts/parent_form.html", {
                            "form": form,
                            "title": "Edit Parent",
                            "editing": True,
                        })
                else:
                    messages.success(request, "✅ Parent updated successfully.")

                return redirect("manage_parents")

            messages.error(request, "⚠️ Please fix the errors below.")

        else:
            initial_data = {
                'username': user.username or "",
                'email': user.email or "",
                'fullname': f"{user.first_name} {user.last_name}".strip(),
            }
            form = ParentProfileForm(instance=parent, initial=initial_data)

        return render(request, "accounts/parent_form.html", {
            "form": form,
            "title": "Edit Parent",
            "editing": True,
        })

    except IntegrityError as e:
        messages.error(request, f"❌ Database error: {str(e)}")
        return redirect("manage_parents")
    except Exception as e:
        messages.error(request, f"❌ Unexpected error occurred: {str(e)}")
        return redirect("manage_parents")



# ✅ Delete parent

@login_required
def delete_parent(request, pk):
    parent = get_object_or_404(Parent, pk=pk)
    user = get_object_or_404(User, parent_profile__pk=pk)

    parent_name = parent.user or user.get_full_name() or user.username

    # Delete both parent profile and linked user
    user.delete()

    messages.success(request, f"🗑️ Parent '{parent_name}' has been deleted successfully.")
    return redirect('manage_parents')




from django.http import HttpResponse
from django.db.models import Avg
import traceback

@login_required
def teacher_dashboard(request):
    try:
        teacher = request.user

        total_results = ResultRecord.objects.filter(teacher=teacher).count()
        total_subjects = Subject.objects.filter(teacher=teacher).count()
        total_classes = (
            ResultRecord.objects.filter(teacher=teacher)
            .values("classroom")
            .distinct()
            .count()
        )

        avg_score = (
            ResultRecord.objects.filter(teacher=teacher)
            .aggregate(avg=Avg("total_score"))
            .get("avg") or 0
        )

        recent_results = (
            ResultRecord.objects.filter(teacher=teacher)
            .select_related("student", "subject", "session")
            .order_by("-date_recorded")[:6]
        )

        term_stats = (
            ResultRecord.objects.filter(teacher=teacher)
            .values("term")
            .annotate(avg_score=Avg("total_score"))
            .order_by("term")
        )

        terms = [item["term"] for item in term_stats]
        avg_scores = [float(item["avg_score"]) for item in term_stats if item["avg_score"]]

        unmarked_scripts = ResultRecord.objects.filter(
            teacher=teacher, total_score=0
        ).count()

        return render(
            request,
            "accounts/teacher_dashboard.html",
            {
                "total_results": total_results,
                "total_subjects": total_subjects,
                "total_classes": total_classes,
                "avg_score": round(avg_score, 2),
                "recent_results": recent_results,
                "terms": terms,
                "avg_scores": avg_scores,
                "unmarked_scripts": unmarked_scripts,
            },
        )

    except Exception as e:
        error_text = f"<h2>Error Loading Teacher Dashboard</h2><pre>{traceback.format_exc()}</pre>"
        return HttpResponse(error_text)


@login_required
def student_dashboard(request):
    student = request.user.student

    # Academics
    summaries = ResultSummary.objects.filter(student=student).order_by("-date_generated")[:3]
    recent_results = ResultRecord.objects.filter(student=student).select_related(
        "subject", "session"
    ).order_by("-date_recorded")[:6]

    avg_score = ResultRecord.objects.filter(student=student).aggregate(avg=Avg("total_score"))["avg"] or 0
    best_subject = ResultRecord.objects.filter(student=student).order_by("-total_score").first()
    worst_subject = ResultRecord.objects.filter(student=student).order_by("total_score").first()

    term_stats = (
        ResultRecord.objects.filter(student=student)
        .values("term")
        .annotate(avg_score=Avg("total_score"))
        .order_by("term")
    )

    terms = [item["term"] for item in term_stats]
    avg_scores = [float(item["avg_score"]) for item in term_stats]

    # Finance
    fee_records = StudentFeeRecord.objects.filter(student=student)
    total_due = fee_records.aggregate(total=Sum("total_amount"))["total"] or 0
    total_paid = fee_records.aggregate(total=Sum("amount_paid"))["total"] or 0
    total_balance = total_due - total_paid
    cleared_fees = fee_records.filter(is_cleared=True).count()
    uncleared_fees = fee_records.filter(is_cleared=False).count()
    invoices = Invoice.objects.filter(student=student).order_by("-date_issued")[:5]

    return render(request, "accounts/student_dashboard.html", {
        "summaries": summaries,
        "recent_results": recent_results,
        "avg_score": round(avg_score, 2),
        "best_subject": best_subject,
        "worst_subject": worst_subject,
        "terms": terms,
        "avg_scores": avg_scores,
        "fee_records": fee_records,
        "total_due": total_due,
        "total_paid": total_paid,
        "total_balance": total_balance,
        "cleared_fees": cleared_fees,
        "uncleared_fees": uncleared_fees,
        "invoices": invoices,
    })


@login_required
def accountant_dashboard(request):
    total_students = Student.objects.count()
    total_invoices = Invoice.objects.count()

    invoice_stats = Invoice.objects.aggregate(
        total_paid=Sum('total_paid'),
        total_due=Sum('total_due'),
    )

    total_paid = float(invoice_stats['total_paid'] or 0)
    total_due = float(invoice_stats['total_due'] or 0)
    total_balance = total_due - total_paid


    fully_paid = Invoice.objects.filter(is_paid=True).count()
    partially_paid = Invoice.objects.filter(balance__gt=0, total_paid__gt=0).count()
    unpaid = Invoice.objects.filter(total_paid=0).count()
    
    pending_total = Invoice.objects.filter(balance__gt=0, total_paid__gt=0).aggregate(
        total=Sum("balance")
    )["total"] or 0

    # Last 6 months data
    today = timezone.now().date()
    months, revenues = [], []
    
    for i in range(5, -1, -1):
        month_start = today.replace(day=1) - timedelta(days=30 * i)
        month_end = (month_start + timedelta(days=31)).replace(day=1)
        label = month_start.strftime("%b %Y")
        
        total = Payment.objects.filter(
            date_paid__gte=month_start, date_paid__lt=month_end
        ).aggregate(total=Sum("amount"))["total"] or 0
        
        months.append(label)
        revenues.append(float(total))

    # Update finance summary
    FinanceSummary.objects.update_or_create(
        id=1,
        defaults={
            'total_students': total_students,
            'total_invoices': total_invoices,
            'total_fees_paid': total_paid,
            'total_fees_pending': pending_total,
            'total_fees_unpaid': total_balance,
        }
    )

    invoices = Invoice.objects.select_related("student").order_by("-date_issued")[:5]

    return render(request, "accounts/accountant_dashboard.html", {
        "total_students": total_students,
        "total_invoices": total_invoices,
        "total_paid": total_paid,
        "total_due": total_due,
        "total_balance": total_balance,
        "fully_paid": fully_paid,
        "partially_paid": partially_paid,
        "unpaid": unpaid,
        "pending_total": pending_total,
        "monthly_labels": months,
        "monthly_revenue": revenues,
        "invoices": invoices,
    })



# ✅ Role check using your CustomUser.role field
def is_parent(user):
    return user.is_authenticated and user.role.lower() == "parent"

@login_required
@user_passes_test(is_parent, login_url="custom_login")
def parent_dashboard(request):
    # ✅ Get parent profile linked to the logged-in user
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        messages.error(request, "Parent profile not found. Please contact the administrator.")
        return redirect("custom_login")

    # ✅ Preload all children + related data efficiently
    children = parent.children.select_related("user").prefetch_related(
        "results__session", "results__subject", "studentfeerecord_set__payments"
    )

    dashboard_data = []

    for child in children:
        # Gather result-related data
        results = child.results.filter(~Q(test_score=0, exam_score=0))
        latest_result = results.order_by("-date_recorded").first()

        grade = latest_result.grade if latest_result else "N/A"
        score = latest_result.total_score if latest_result else "N/A"

        avg_total = results.aggregate(total=Sum("total_score"))["total"] or 0
        count = results.count()
        average_score = round(avg_total / count, 2) if count else 0

        # Gather fee-related data
        fee_records = StudentFeeRecord.objects.filter(student=child)
        total_fee = fee_records.aggregate(total=Sum("total_amount"))["total"] or 0
        total_paid = fee_records.aggregate(total=Sum("amount_paid"))["total"] or 0
        pending_balance = total_fee - total_paid

        last_payment = (
            Payment.objects.filter(student_fee__student=child)
            .order_by("-date_paid")
            .first()
        )

        # Combine all data for each child
        dashboard_data.append({
            "child": child,
            "grade": grade,
            "score": score,
            "average_score": average_score,
            "total_subjects": count,
            "total_fee": total_fee,
            "total_paid": total_paid,
            "pending_balance": pending_balance,
            "last_payment": last_payment,
        })

    # ✅ Render the dashboard
    return render(request, "accounts/parent_dashboard.html", {
        "parent": parent,
        "dashboard_data": dashboard_data,
    })


# ==========================================
# 5️⃣ USER MANAGEMENT
# ==========================================
@login_required
def manage_students(request):
    query = request.GET.get('q', '')
    status = request.GET.get('status', 'all')
    students = Student.objects.select_related('user', 'current_class')

    if query:
        students = students.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(student_id__icontains=query) |
            Q(current_class__name__icontains=query)
        )

    if status == "active":
        students = students.filter(user__is_active=True)
    elif status == "inactive":
        students = students.filter(user__is_active=False)

    context = {
        'students': students,
        'total_students': Student.objects.count(),
        'query': query,
        'status': status,
    }
    return render(request, 'accounts/manage_students.html', context)




@login_required
def add_student(request):
    if request.method == 'POST':
        user_form = UserForm(request.POST, request.FILES)
        student_form = StudentForm(request.POST, request.FILES)

        if user_form.is_valid() and student_form.is_valid():

            username = request.POST.get('username')
            email = request.POST.get('email', "").strip()

            # Check username uniqueness
            if CustomUser.objects.filter(username=username).exists():
                messages.error(request, "⚠️ Username already exists.")
                return render(request, 'accounts/add_student.html', {
                    'user_form': user_form,
                    'student_form': student_form,
                })

            # ✔ Check email uniqueness ONLY if provided
            if email:
                if CustomUser.objects.filter(email=email).exists():
                    messages.error(request, "⚠️ Email already exists.")
                    return render(request, 'accounts/add_student.html', {
                        'user_form': user_form,
                        'student_form': student_form,
                    })

            # Save user
            user = user_form.save(commit=False)
            user.role = 'student'
            user.set_password('student123')

            # If email was blank, store NULL
            if not email:
                user.email = None

            user.save()

            # Save student
            student = student_form.save(commit=False)
            student.user = user
            student.save()

            messages.success(request, "✅ Student added successfully!")
            return redirect('manage_students')

    else:
        user_form = UserForm()
        student_form = StudentForm()

    return render(request, 'accounts/add_student.html', {
        'user_form': user_form,
        'student_form': student_form,
    })



@login_required
def manage_teachers(request):
    query = request.GET.get("q", "").strip()
    teachers = Teacher.objects.select_related("user").all()

    if query:
        teachers = teachers.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(staff_id__icontains=query)
            | Q(department__icontains=query)
            | Q(qualification__icontains=query)
        )

    return render(request, "accounts/manage_teachers.html", {"teachers": teachers, "query": query})

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
import csv



User = get_user_model()

# ==========================================
# ➕ ADD TEACHER
# ==========================================
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.models import Group
from django.db import IntegrityError
from .models import CustomUser, Teacher
from .forms import UserForm, TeacherProfileForm





def add_teacher(request):
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        teacher_form = TeacherProfileForm(request.POST)

        if user_form.is_valid() and teacher_form.is_valid():
            try:
                # 1️⃣ Create the user first (this triggers post_save -> auto Teacher)
                user = user_form.save(commit=False)
                user.set_password("teacher123")  # default password
                user.role = 'teacher'
                user.save()

                # 2️⃣ Assign Teacher group
                teacher_group, _ = Group.objects.get_or_create(name='Teacher')
                user.groups.add(teacher_group)

                # 3️⃣ Get the auto-created Teacher profile from the signal
                teacher = getattr(user, 'teacher_profile', None)
                if not teacher:
                    # Safety fallback (in case signal didn’t run)
                    teacher = Teacher.objects.create(user=user, staff_id=f"T-{user.id}")

                # 4️⃣ Update teacher profile with form data
                teacher_form = TeacherProfileForm(request.POST, instance=teacher)
                if teacher_form.is_valid():
                    teacher_form.save()
                    messages.success(request, "✅ Teacher added successfully!")
                    return redirect('manage_teachers')
                else:
                    messages.error(request, "❌ There were errors in the teacher form.")

            except IntegrityError as e:
                messages.error(request, f"❌ Database error: {str(e)}")
            except Exception as e:
                messages.error(request, f"❌ Unexpected error: {str(e)}")

        else:
            messages.error(request, "❌ Please correct the errors below.")

    else:
        user_form = UserForm()
        teacher_form = TeacherProfileForm()

    return render(request, 'accounts/add_teacher.html', {
        'user_form': user_form,
        'teacher_form': teacher_form,
    })

# ==========================================
# 📥 IMPORT TEACHERS (CSV Upload)
# ==========================================
import csv
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.contrib import messages
from django.shortcuts import render, redirect
from accounts.models import Teacher

User = get_user_model()


def import_teachers(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']

        # Validate file type
        if not file.name.endswith('.csv'):
            messages.error(request, '❌ Please upload a CSV file.')
            return redirect('import_teachers')

        decoded_file = file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)

        created_count = 0
        skipped = 0

        for row in reader:
            try:
                full_name = (row.get('full_name') or "").strip()
                email = (row.get('email') or "").strip()
                subject = row.get('subject', "").strip()

                # Skip rows with no name
                if not full_name:
                    skipped += 1
                    continue

                # Generate username even if email missing
                if email:
                    username = email.split("@")[0]
                else:
                    # fallback username (unique)
                    username = full_name.replace(" ", "").lower()[:10]

                # Make username unique
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                # Split names
                parts = full_name.split()
                first_name = parts[0]
                last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

                # ------------------------------------
                # CREATE USER + auto Teacher profile
                # ------------------------------------
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username,
                        email=email if email else None,
                        first_name=first_name,
                        last_name=last_name,
                        password="teacher123",   # default password
                        role="teacher"
                    )

                    # Assign Teacher group
                    teacher_group, _ = Group.objects.get_or_create(name="Teacher")
                    user.groups.add(teacher_group)

                    # Get auto-created Teacher profile (from signal)
                    teacher = getattr(user, "teacher_profile", None)
                    if not teacher:
                        # fallback if signal didn’t fire
                        teacher = Teacher.objects.create(
                            user=user,
                            staff_id=f"T-{user.id}"
                        )

                    # Set subject if available
                    if subject:
                        teacher.subject = subject
                        teacher.save()

                created_count += 1

            except IntegrityError:
                skipped += 1
                continue
            except Exception as e:
                skipped += 1
                continue

        messages.success(request,
            f"✅ Imported: {created_count} teachers | ⛔ Skipped: {skipped}"
        )
        return redirect('manage_teachers')

    return render(request, 'accounts/import_teachers.html')



from django.db import IntegrityError
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Teacher, CustomUser
from .forms import UserForm, TeacherProfileForm

@login_required
def edit_teacher(request, pk):
    try:
        teacher = get_object_or_404(Teacher, pk=pk)
        user = teacher.user

        if request.method == "POST":
            user_form = UserForm(request.POST, instance=user)
            teacher_form = TeacherProfileForm(request.POST, instance=teacher)

            new_password = request.POST.get("new_password")
            confirm_password = request.POST.get("confirm_password")
            is_active = request.POST.get("is_active")

            if user_form.is_valid() and teacher_form.is_valid():

                # --- USERNAME CHECK ---
                username = (user_form.cleaned_data.get("username") or "").strip()
                if CustomUser.objects.filter(username=username).exclude(pk=user.pk).exists():
                    messages.error(request, "❌ Username already exists.")
                    return render(request, "accounts/edit_teacher.html", locals())

                # --- EMAIL CHECK ---
                email = (user_form.cleaned_data.get("email") or "").strip()
                if email and CustomUser.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    messages.error(request, "❌ Email already exists.")
                    return render(request, "accounts/edit_teacher.html", locals())

                # --- UPDATE USER ---
                user.username = username
                user.email = email
                user_form.save()

                # --- UPDATE TEACHER PROFILE ---
                teacher_form.save()  # staff_id excluded, safe

                # --- OPTIONAL PASSWORD RESET ---
                if new_password:
                    if new_password == confirm_password:
                        user.set_password(new_password)
                        user.save()
                        messages.info(request, f"🔑 Password reset for {user.username}.")
                    else:
                        messages.error(request, "❌ Passwords do not match.")
                        return render(request, "accounts/edit_teacher.html", locals())

                # --- ACTIVE STATUS ---
                user.is_active = bool(is_active)
                user.save(update_fields=["is_active"])

                messages.success(request, "✅ Teacher updated successfully.")
                return redirect("manage_teachers")

        else:
            user_form = UserForm(instance=user)
            teacher_form = TeacherProfileForm(instance=teacher)

        return render(request, "accounts/edit_teacher.html", {
            "user_form": user_form,
            "teacher_form": teacher_form,
            "teacher": teacher,
        })

    except IntegrityError as e:
        messages.error(request, f"❌ Database error: {str(e)}")
        return redirect("manage_teachers")
    except Exception as e:
        messages.error(request, f"❌ Unexpected error occurred: {str(e)}")
        return redirect("manage_teachers")



from academics.models import ClassRoom  # Make sure this import matches your project
import logging
logger = logging.getLogger(__name__)

@login_required
def edit_student(request, pk):
    try:
        student = get_object_or_404(Student, pk=pk)
        user = student.user

        # GET classrooms for datalist
        classrooms = ClassRoom.objects.all()

        if request.method == "POST":
            full_name = request.POST.get("full_name")
            email = request.POST.get("email")
            current_class_name = request.POST.get("current_class")  # string from input
            new_password = request.POST.get("new_password")
            confirm_password = request.POST.get("confirm_password")
            is_active = request.POST.get("is_active")

            # Update user info
            name_parts = full_name.split(" ", 1)
            user.first_name = name_parts[0]
            user.last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Fix: allow blank email without unique constraint error
            if not email or email.strip() == "":
                user.email = None
            else:
                user.email = email


            # Optional password reset
            if new_password:
                if new_password == confirm_password:
                    user.set_password(new_password)
                    messages.info(request, f"🔑 Password for {user.username} has been reset successfully.")
                else:
                    messages.error(request, "❌ Passwords do not match.")
                    return render(request, "accounts/edit_student.html", {
                        "student": student,
                        "classrooms": classrooms
                    })

            # Active toggle
            user.is_active = bool(is_active)
            user.save()

            # Get or create ClassRoom safely
            classroom, _ = ClassRoom.objects.get_or_create(name=current_class_name)
            student.current_class = classroom
            student.save()

            messages.success(request, "✅ Student and user details updated successfully.")
            return redirect("manage_students")

        # GET request
        context = {"student": student, "classrooms": classrooms}
        return render(request, "accounts/edit_student.html", context)

    except Exception as e:
        # Log full error details
        logger.error(f"Error in edit_student: {e}", exc_info=True)

        # Show developer-friendly error message on frontend
        messages.error(request, f"⚠️ An unexpected error occurred: {str(e)}")

        # Return page with the error visible
        return render(request, "accounts/edit_student.html", {
            "student": student,
            "classrooms": classrooms,
            "error_message": str(e)
        })





@login_required
def delete_teacher(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == "POST":
        user=teacher.user
        teacher.delete()
        user.delete()
        messages.success(request, "🗑️ Teacher deleted successfully.")
        return redirect("manage_teachers")

    return render(request, "accounts/confirm_delete_teacher.html", {"teacher": teacher})



@login_required
def delete_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == "POST":
        # Also delete associated user
        user = student.user
        student.delete()
        user.delete()

        messages.success(request, "🗑️ Student and account deleted successfully.")
        return redirect("manage_students")

    return render(request, "accounts/confirm_delete_student.html", {"student": student})




def is_parent(user):
    return getattr(user, "role", "").lower() == "parent"


@login_required
def child_performance(request):
    """Allow only parent users to view child performance overview."""
    # Ensure the logged-in user is a parent
    if not is_parent(request.user):
        messages.error(request, "Access denied. Only parents can view this page.")
        return redirect("dashboard")

    # Get the parent's profile safely
    parent = Parent.objects.filter(user=request.user).first()
    if not parent:
        messages.error(request, "Parent profile not found.")
        return redirect("custom_login")

    # Fetch all linked children
    children = parent.children.select_related("user").all()

    return render(request, "results/child_performance.html", {
        "parent": parent,
        "children": children,
    })


@login_required
def child_result(request, student_id):
    """Show the result of a particular child, restricted to the parent."""
    # Ensure only parent can access
    if not is_parent(request.user):
        messages.error(request, "Access denied. Only parents can view this page.")
        return redirect("dashboard")

    parent = Parent.objects.filter(user=request.user).first()
    if not parent:
        messages.error(request, "Parent profile not found.")
        return redirect("custom_login")

    # Fetch the child and ensure it belongs to this parent
    child = get_object_or_404(Student, id=student_id)
    if not parent.children.filter(id=child.id).exists():
        messages.error(request, "You are not authorized to view this child’s results.")
        return redirect("child_performance")

    # Filtering logic
    sessions = Session.objects.all().order_by("-start_date")
    selected_session_id = request.GET.get("session")
    selected_term = request.GET.get("term")

    results = ResultRecord.objects.filter(student=child).exclude(
        Q(test_score=0) & Q(exam_score=0)
    )

    if selected_session_id:
        results = results.filter(session_id=selected_session_id)
    if selected_term:
        results = results.filter(term=selected_term)

    terms = results.values_list("term", flat=True).distinct()

    return render(request, "results/child_result.html", {
        "child": child,
        "results": results,
        "sessions": sessions,
        "selected_session_id": selected_session_id,
        "terms": terms,
        "selected_term": selected_term,
    })


from .forms import ProfileUpdateForm, UserForm, CustomPasswordChangeForm, UserEmailForm
from django.contrib.auth import update_session_auth_hash

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth import update_session_auth_hash

from .forms import ProfileUpdateForm, UserEmailForm, CustomPasswordChangeForm
from .models import Student, Teacher, Admin, Accountant, Parent  # import all roles


@login_required
def edit_profile(request):
    user = request.user

    role_model_map = {
        "student": Student,
        "teacher": Teacher,
        "admin": Admin,
        "accountant": Accountant,
        "parent": Parent,
    }

    model = role_model_map.get(user.role)
    profile = None

    if model:
        profile, _ = model.objects.get_or_create(user=user)

    if request.method == "POST":
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        email_form = UserEmailForm(request.POST, instance=user)
        password_form = CustomPasswordChangeForm(user, request.POST)

        if "update_profile" in request.POST:
            if profile_form.is_valid() and email_form.is_valid():
                email_form.save()
                profile_form.save()
                messages.success(request, "✅ Profile updated successfully!")
                return redirect("edit_profile")

        elif "change_password" in request.POST:
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "🔒 Password changed successfully!")
                return redirect("edit_profile")
            else:
                messages.error(request, "⚠️ Please correct the password errors below.")

    else:
        profile_form = ProfileUpdateForm(instance=profile)
        email_form = UserEmailForm(instance=user)
        password_form = CustomPasswordChangeForm(user)

    context = {
        "profile_form": profile_form,
        "email_form": email_form,
        "password_form": password_form,
        "profile_data": profile,  # REQUIRED
        "role": user.role.capitalize(),  # optional
    }
    return render(request, "accounts/edit_profile.html", context)


