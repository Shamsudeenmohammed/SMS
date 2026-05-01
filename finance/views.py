# ===============================================
# ✅ Clean & Optimized Imports
# ===============================================

# Django Core Imports
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import F, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone


# Python Standard Library
import io
import os
import csv
from datetime import datetime
from io import BytesIO

# Third-Party Libraries
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Project-Level Imports
from .models import FinanceSummary, Invoice, Payment, StudentFeeRecord, FeeType, BulkFeeAssignment
from .forms import FeeTypeForm, BulkFeeForm, StudentFeeForm, PaymentForm,BulkFeeCreationForm
from academics.models import Session
from accounts.models import Student, Teacher 
from accounts.models import Parent
from .utils import update_finance_summary






def manage_invoices(request):
    """
    Display all invoices and summary totals.
    The template can auto-refresh via the invoices_json endpoint.
    """
    # Efficient queryset: prefetch related data and order by latest issued
    invoices = Invoice.objects.select_related("student", "session").order_by("-date_issued")

    # Compute summary safely
    aggregates = invoices.aggregate(
        total_due=Sum("total_due"),
        total_paid=Sum("total_paid"),
        total_balance=Sum("balance")
    )

    context = {
        "invoices": invoices,
        "total_due": aggregates["total_due"] or 0,
        "total_paid": aggregates["total_paid"] or 0,
        "total_balance": aggregates["total_balance"] or 0,
    }

    return render(request, "finance/manage_invoices.html", context)


# ===========================
# 🔍 Student Search for Select2

@login_required
def student_search(request):
    """AJAX endpoint for Select2 student search."""
    term = request.GET.get('term', '')
    students = Student.objects.filter(full_name__icontains=term)[:20]  # limit for performance
    results = [
        {'id': s.id, 'text': f"{s.full_name} - {s.current_class}"}
        for s in students
    ]
    return JsonResponse({'results': results})



# ===========================
# 💸 Record Payment
# ===========================
@login_required
def record_payment(request):
    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)


            # 🔹 Update related student fee record
            fee_record = payment.student_fee
            fee_record.amount_paid += payment.amount
            fee_record.save()  # auto-updates balance & is_cleared if defined in model logic


            # 🔹 Automatically set the receiver to the logged-in user
            payment.received_by = request.user 
            # 🔹 Save the payment record
            payment.save()

            # 🔹 Update finance summary dynamically
            update_finance_summary()

            messages.success(request, "Payment recorded successfully.")
            return redirect("manage_invoices")
    else:
        form = PaymentForm()

    return render(request, "finance/record_payment.html", {"form": form})



#===========================
# 🔁 Finance Summary Updater
#===========================
def update_finance_summary():
    """Recalculate and refresh the FinanceSummary after any payment."""
    # Aggregate data from StudentFeeRecord
    total_students = StudentFeeRecord.objects.values("student").distinct().count()
    total_due = StudentFeeRecord.objects.aggregate(total=Sum("total_amount"))["total"] or 0
    total_paid = StudentFeeRecord.objects.aggregate(total=Sum("amount_paid"))["total"] or 0
    total_balance = StudentFeeRecord.objects.aggregate(total=Sum("balance"))["total"] or 0

    fully_paid = StudentFeeRecord.objects.filter(is_cleared=True).count()
    partially_paid = StudentFeeRecord.objects.filter(amount_paid__gt=0, is_cleared=False).count()
    unpaid = StudentFeeRecord.objects.filter(amount_paid=0).count()

    # Get or create the single summary record
    summary, _ = FinanceSummary.objects.get_or_create(id=1)

    # Update fields (match your model names)
    summary.total_students = total_students
    summary.total_invoices = Invoice.objects.count()
    summary.total_fees_paid = total_paid
    summary.total_fees_pending = total_balance
    summary.total_fees_unpaid = total_due - total_paid
    summary.save()



# ===========================
# 📊 JSON Summary Endpoint
# ===========================
@login_required
def finance_summary_json(request):
    total_students = Student.objects.count()  # all students
    students_with_fees = Invoice.objects.values('student').distinct().count()  # students with invoices

    total_invoices = Invoice.objects.count()
    total_paid = Invoice.objects.aggregate(total=Sum('total_paid'))['total'] or 0
    total_due = Invoice.objects.aggregate(total=Sum('total_due'))['total'] or 0
    total_balance = total_due - total_paid
    pending_total = Invoice.objects.filter(balance__gt=0, total_paid__gt=0).aggregate(total=Sum('balance'))['total'] or 0

    data = {
        "total_students": total_students,
        "students_with_fees": students_with_fees,
        "total_invoices": total_invoices,
        "total_paid": float(total_paid),
        "total_due": float(total_due),
        "total_balance": float(total_balance),
        "pending_total": float(pending_total),
    }
    return JsonResponse(data)



@login_required
def invoices_json(request):
    """
    Return invoices + summary as JSON for live updates.
    Converts Decimal fields to floats so JsonResponse won't choke.
    """
    qs = Invoice.objects.select_related("student", "session").order_by("-date_issued")

    invoices_list = []
    for inv in qs:
        # Student display: use get_full_name if available, fallback to string
        student_name = inv.student.get_full_name() if hasattr(inv.student, "get_full_name") else str(inv.student)
        session_label = str(inv.session) if inv.session else ""

        invoices_list.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "student_name": student_name,
            "session": session_label,
            "term": inv.term,
            "total_due": float(inv.total_due),
            "total_paid": float(inv.total_paid),
            "balance": float(inv.balance),
            "is_paid": bool(inv.is_paid),
            "date_issued": inv.date_issued.isoformat() if inv.date_issued else None,
        })

    # Totals (safe cast to float)
    total_due = float(Invoice.objects.aggregate(total=Sum("total_due"))["total"] or 0)
    total_paid = float(Invoice.objects.aggregate(total=Sum("total_paid"))["total"] or 0)
    total_balance = float(Invoice.objects.aggregate(total=Sum("balance"))["total"] or 0)

    return JsonResponse({
        "invoices": invoices_list,
        "summary": {
            "total_due": total_due,
            "total_paid": total_paid,
            "total_balance": total_balance,
        }
    })

#==========================
# 📄 Download Invoice as PDF
@login_required
def download_invoice_pdf(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{invoice.invoice_number}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    
    # Corrected Capitalization
    brand_color = colors.HexColor("#1A237E")
    text_muted = colors.HexColor("#424242")

    # === Header / Branding ===
    p.setFillColor(brand_color)
    p.rect(0, height - 100, width, 100, fill=True, stroke=False)
    
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 22)
    p.drawCentredString(width / 2, height - 55, "CENTER FOR GLORY SCHOOL")
    
    p.setFont("Helvetica", 11)
    p.drawCentredString(width / 2, height - 75, "Official Payment Receipt & Invoice Summary")

    # === Invoice Details ===
    p.setFillColor(colors.black)
    y = height - 140
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Billed To:")
    p.setFont("Helvetica", 12)
    p.drawString(50, y - 20, f"{invoice.student.get_full_name() if hasattr(invoice.student, 'get_full_name') else str(invoice.student)}")
    
    p.setFont("Helvetica-Bold", 10)
    p.drawRightString(width - 50, y, f"Invoice No: {invoice.invoice_number}")
    p.setFont("Helvetica", 10)
    p.drawRightString(width - 50, y - 15, f"Date: {invoice.date_issued.strftime('%B %d, %Y')}")
    p.drawRightString(width - 50, y - 30, f"Session: {invoice.session} ({invoice.term})")

    # === Table Header ===
    y -= 80
    p.setStrokeColor(brand_color)
    p.setLineWidth(1)
    p.line(50, y + 15, width - 50, y + 15)
    
    p.setFont("Helvetica-Bold", 11)
    p.drawString(60, y, "Description")
    p.drawRightString(width - 60, y, "Amount")
    p.line(50, y - 10, width - 50, y - 10)

    # === Table Content ===
    y -= 30
    p.setFont("Helvetica", 11)
    items = [
        ("Total Tuition & Fees Due", f"GH₵ {invoice.total_due}"),
        ("Total Amount Paid", f"GH₵ {invoice.total_paid}"),
    ]

    for label, amt in items:
        p.drawString(60, y, label)
        p.drawRightString(width - 60, y, amt)
        y -= 25

    # === Summary Box ===
    y -= 20
    p.setFillColor(colors.whitesmoke)
    p.rect(300, y - 40, width - 350, 60, fill=True, stroke=False)
    
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 13)
    p.drawString(310, y, "Outstanding Balance")
    p.drawRightString(width - 60, y, f"GH₵ {invoice.balance}")
    
    y -= 25
    status_color = colors.green if invoice.is_paid else colors.red
    p.setFillColor(status_color)
    p.setFont("Helvetica-Bold", 11)
    status_text = "STATUS: FULLY PAID" if invoice.is_paid else "STATUS: PAYMENT PENDING"
    p.drawString(310, y, status_text)

    # === Footer ===
    p.setStrokeColor(colors.lightgrey)
    p.line(50, 100, width - 50, 100)
    p.setFillColor(text_muted)
    p.setFont("Helvetica-Oblique", 9)
    p.drawCentredString(width / 2, 80, "Thank you for choosing Center for Glory School.")
    p.drawCentredString(width / 2, 65, "This is a computer-generated document. No signature is required.")

    p.showPage()
    p.save()
    return response





# ✅ Restrict access to Accountant & Admin/Principal
def is_finance_user(user):
    return user.is_authenticated and user.role in ["admin", "principal", "accountant"]



# =============================
# MAIN REPORT VIEW
# =============================
@login_required
@user_passes_test(is_finance_user)
def financial_report(request):
    # --- Filters ---
    session_id = request.GET.get("session")
    term = request.GET.get("term")
    status_filter = request.GET.get("status")
    search_query = request.GET.get("search")  # ✅ added search input

    # --- Base Query ---
    report_data = (
        StudentFeeRecord.objects.values(
            "student__user__first_name",
            "student__user__last_name",
            "session__name",
            "term",
        )
        .annotate(
            total_due=Sum("total_amount"),
            total_paid=Sum("amount_paid"),
            balance=Sum(F("total_amount") - F("amount_paid")),
        )
        .order_by("student__user__first_name")
    )
    # --- Add computed fields ---
    for record in report_data:
        # Assuming the Student model has a field like 'student_id' (e.g., registration number)
        student_obj = Student.objects.filter(
            user__first_name=record["student__user__first_name"],
            user__last_name=record["student__user__last_name"]
        ).first()
        record["student_id"] = student_obj.student_id if student_obj else "N/A"

        if record["balance"] < 0:
            record["status"] = "Overpaid"
        elif record["balance"] == 0:
            record["status"] = "Cleared"
        else:
            record["status"] = "Owing"

    # --- Apply Filters ---
    if session_id:
        session_name = Session.objects.get(id=session_id).name
        report_data = [r for r in report_data if str(r["session__name"]) == session_name]
    if term:
        report_data = [r for r in report_data if r["term"] == term]
    if status_filter:
        report_data = [r for r in report_data if r["status"].lower() == status_filter.lower()]
    if search_query:  # ✅ search by student ID instead of name
        report_data = [
            r for r in report_data
            if search_query.lower() in str(r["student_id"]).lower()
        ]


    # --- Render HTML Page ---
    sessions = Session.objects.all()
    context = {
        "report_data": report_data,
        "sessions": sessions,
    }
    return render(request, "finance/financial_report.html", context)



# =============================
# EXPORT TO EXCEL
# =============================
@login_required
@user_passes_test(is_finance_user)
def export_financial_report_excel(request):
    # Fetch the same data logic
    session_id = request.GET.get("session")
    term = request.GET.get("term")
    status_filter = request.GET.get("status")

    report_data = (
        StudentFeeRecord.objects.values(
            "student__user__first_name",
            "student__user__last_name",
            "session__name",
            "term",
        )
        .annotate(
            total_due=Sum("total_amount"),
            total_paid=Sum("amount_paid"),
            balance=Sum(F("total_amount") - F("amount_paid")),
        )
        .order_by("student__user__first_name")
    )

    # Add computed fields
    for record in report_data:
        record["student_name"] = f"{record['student__user__first_name']} {record['student__user__last_name']}"
        if record["balance"] < 0:
            record["status"] = "Overpaid"
        elif record["balance"] == 0:
            record["status"] = "Cleared"
        else:
            record["status"] = "Owing"

    # Apply Filters
    if session_id:
        session_name = Session.objects.get(id=session_id).name
        report_data = [r for r in report_data if str(r["session__name"]) == session_name]
    if term:
        report_data = [r for r in report_data if r["term"] == term]
    if status_filter:
        report_data = [r for r in report_data if r["status"].lower() == status_filter.lower()]

    # Export to Excel
    df = pd.DataFrame(report_data)
    df = df[["student_name", "session__name", "term", "total_due", "total_paid", "balance", "status"]]
    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Financial Report")
    output.seek(0)

    response = HttpResponse(
        output,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="financial_report.xlsx"'
    return response


# =============================
# EXPORT TO PDF
# =============================
@login_required
@user_passes_test(is_finance_user)
def export_financial_report_pdf(request):
    session_id = request.GET.get("session")
    term = request.GET.get("term")
    status_filter = request.GET.get("status")

    report_data = (
        StudentFeeRecord.objects.values(
            "student__user__first_name",
            "student__user__last_name",
            "session__name",
            "term",
        )
        .annotate(
            total_due=Sum("total_amount"),
            total_paid=Sum("amount_paid"),
            balance=Sum(F("total_amount") - F("amount_paid")),
        )
        .order_by("student__user__first_name")
    )

    for record in report_data:
        record["student_name"] = f"{record['student__user__first_name']} {record['student__user__last_name']}"
        if record["balance"] < 0:
            record["status"] = "Overpaid"
        elif record["balance"] == 0:
            record["status"] = "Cleared"
        else:
            record["status"] = "Owing"

    if session_id:
        session_name = Session.objects.get(id=session_id).name
        report_data = [r for r in report_data if str(r["session__name"]) == session_name]
    if term:
        report_data = [r for r in report_data if r["term"] == term]
    if status_filter:
        report_data = [r for r in report_data if r["status"].lower() == status_filter.lower()]

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="financial_report.pdf"'
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    # Title
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, height - 40, "Students Financial Report")

    # Table header
    y = height - 80
    p.setFont("Helvetica-Bold", 10)
    headers = ["Student Name", "Session", "Term", "Total Due", "Total Paid", "Balance", "Status"]
    x_positions = [40, 180, 300, 400, 480, 560, 640]

    for i, header in enumerate(headers):
        p.drawString(x_positions[i], y, header)

    # Table rows
    y -= 20
    p.setFont("Helvetica", 9)
    for record in report_data:
        if y < 50:
            p.showPage()
            p.setFont("Helvetica-Bold", 10)
            y = height - 50
            for i, header in enumerate(headers):
                p.drawString(x_positions[i], y, header)
            y -= 20
            p.setFont("Helvetica", 9)

        p.drawString(x_positions[0], y, record["student_name"])
        p.drawString(x_positions[1], y, record["session__name"])
        p.drawString(x_positions[2], y, record["term"])
        p.drawRightString(x_positions[3] + 40, y, f"{record['total_due']:.2f}")
        p.drawRightString(x_positions[4] + 40, y, f"{record['total_paid']:.2f}")
        p.drawRightString(x_positions[5] + 40, y, f"{record['balance']:.2f}")
        p.drawString(x_positions[6], y, record["status"])
        y -= 18

    p.save()
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response


# =============================
# STUDENT VIEW: My Fees

@login_required
def student_fees(request):
    # Get the logged-in student's fee records
    student = getattr(request.user, 'student', None)
    if not student:
        return render(request, "finance/student_fees.html", {"error": "No student record found."})

    fees = StudentFeeRecord.objects.filter(student=student).select_related("fee_type", "session")

    return render(request, "finance/student_fees.html", {"fees": fees})


# =============================
# STUDENT VIEW: My Invoices

@login_required
def my_invoices(request):
    student = get_object_or_404(Student, user=request.user)
    invoices = Invoice.objects.filter(student=student).order_by("-date_issued")

    return render(request, "finance/my_invoices.html", {
        "invoices": invoices
    })



# =============================
# PARENT VIEW: Child Payment History

@login_required
def parent_payment_history(request):
    parent = Parent.objects.filter(user=request.user).first()

    # Get all payments for this parent's children
    payments = Payment.objects.filter(
        student_fee__student__in=parent.children.all()
    ).select_related("student_fee__student", "received_by")

    # Calculate total across all children
    total_amount_paid = payments.aggregate(total=Sum("amount"))["total"] or 0

    # Calculate total per child
    child_totals = (
        payments.values("student_fee__student__user__first_name", "student_fee__student__user__last_name")
        .annotate(total=Sum("amount"))
        .order_by("student_fee__student__user__first_name")
    )

    context = {
        "payments": payments,
        "total_amount_paid": total_amount_paid,
        "child_totals": child_totals,
    }

    return render(request, "finance/parent_payment_history.html", context)



# ===========================
# 📤 Export Payment History to Excel
# ===========================
@login_required
def export_payment_history_excel(request):
    parent = Parent.objects.filter(user=request.user).first()
    payments = Payment.objects.filter(
        student_fee__student__in=parent.children.all()
    ).select_related('student_fee__student', 'received_by')

    response = HttpResponse(content_type='text/csv')
    filename = f"Payment_History_{timezone.now().strftime('%Y%m%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Child', 'Amount (₵)', 'Method', 'Reference', 'Date Paid', 'Received By'])

    for p in payments:
        writer.writerow([
            p.student_fee.student.user.get_full_name(),
            p.amount,
            p.get_payment_method_display(),
            p.reference,
            timezone.localtime(p.date_paid).strftime('%b %d, %Y %I:%M %p'),
            p.received_by.get_username() if p.received_by else 'N/A',
        ])

    return response




@login_required
def export_payment_history_pdf(request):
    parent = Parent.objects.filter(user=request.user).first()
    payments = Payment.objects.filter(
        student_fee__student__in=parent.children.all()
    ).select_related('student_fee__student', 'received_by')

    # ---- Calculate totals ----
    from django.db.models import Sum
    child_totals = (
        payments.values("student_fee__student__user__first_name", "student_fee__student__user__last_name")
        .annotate(total=Sum("amount"))
        .order_by("student_fee__student__user__first_name")
    )
    total_amount_paid = payments.aggregate(Sum("amount"))["amount__sum"] or 0

    # ---- Prepare PDF ----
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=60,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ---- Header ----
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        alignment=1,
        fontSize=16,
        textColor=colors.HexColor("#1e3a8a"),
        spaceAfter=20,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        alignment=1,
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=15,
    )

    elements.append(Paragraph("💰 Payment History Report", title_style))
    elements.append(Paragraph(
        f"Parent: <b>{request.user.get_full_name()}</b> &nbsp;&nbsp; | &nbsp;&nbsp; Generated on: {timezone.now().strftime('%b %d, %Y, %I:%M %p')}",
        subtitle_style,
    ))
    elements.append(Spacer(1, 12))

    # ---- Payment Table ----
    table_data = [["#", "Child", "Amount (₵)", "Method", "Reference", "Date", "Received By"]]
    for i, p in enumerate(payments, 1):
        table_data.append([
            str(i),
            p.student_fee.student.user.get_full_name(),
            f"{p.amount:.2f}",
            p.get_payment_method_display(),
            p.reference or "-",
            timezone.localtime(p.date_paid).strftime("%b %d, %Y"),
            p.received_by.get_username() if p.received_by else "N/A",
        ])

    table = Table(table_data, repeatRows=1, hAlign="LEFT", colWidths=[30, 100, 70, 70, 80, 80, 80])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # ---- Summary by Child ----
    if child_totals:
        elements.append(Paragraph("🧾 Summary by Child", ParagraphStyle(
            "Header2", parent=styles["Heading2"], textColor=colors.HexColor("#1e3a8a"), spaceAfter=10,
        )))
        child_table_data = [["Child", "Total Paid (₵)"]]
        for c in child_totals:
            full_name = f"{c['student_fee__student__user__first_name']} {c['student_fee__student__user__last_name']}"
            child_table_data.append([full_name, f"{c['total']:.2f}"])

        child_table = Table(child_table_data, repeatRows=1, colWidths=[200, 120])
        child_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(child_table)
        elements.append(Spacer(1, 20))

    # ---- Overall Summary ----
    elements.append(Paragraph("💰 Overall Summary", ParagraphStyle(
        "Header2", parent=styles["Heading2"], textColor=colors.HexColor("#1e3a8a"), spaceAfter=10,
    )))

    summary_data = [
        ["Total Payments Made", str(payments.count())],
        ["Total Amount Paid", f"₵{total_amount_paid:.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[200, 150])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
    ]))
    elements.append(summary_table)

    # ---- Build PDF ----
    pdf.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Payment_History_{timezone.now().strftime("%Y%m%d")}.pdf"'
    return response



# 🎯 Main Fees Management Dashboard
def manage_fees(request):
    total_fees = FeeType.objects.count()
    total_assignments = BulkFeeAssignment.objects.count()
    total_records = StudentFeeRecord.objects.count()
    context = {
        "total_fees": total_fees,
        "total_assignments": total_assignments,
        "total_records": total_records,
    }
    return render(request, "finance/manage_fees.html", context)


# 🧾 Fee Types View
def fee_types(request):
    fees = FeeType.objects.all()
    if request.method == "POST":
        form = FeeTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Fee Type added successfully.")
            return redirect("fee_types")
    else:
        form = FeeTypeForm()
    return render(request, "finance/fee_types.html", {"fees": fees, "form": form})


# 📦 Bulk Fee Assignment
def bulk_fee_assignment(request):
    if request.method == "POST":
        form = BulkFeeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "📦 Bulk Fee Assigned Successfully.")
            return redirect("manage_fees")
    else:
        form = BulkFeeForm()
    return render(request, "finance/bulk_fee_assignment.html", {"form": form})


# 💰 Add Fee Record
def add_fee(request):
    if request.method == "POST":
        form = StudentFeeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "💰 Fee Record Created Successfully.")
            return redirect("manage_fees")
    else:
        form = StudentFeeForm()
    return render(request, "finance/add_fee.html", {"form": form})



def edit_fee_type(request, pk):
    fee = get_object_or_404(FeeType, pk=pk)
    if request.method == "POST":
        form = FeeTypeForm(request.POST, instance=fee)
        if form.is_valid():
            form.save()
            messages.success(request, "Fee type updated successfully.")
            return redirect("fee_types")
    else:
        form = FeeTypeForm(instance=fee)
    return render(request, "finance/edit_fee_type.html", {"form": form, "fee": fee})

def delete_fee_type(request, pk):
    fee = get_object_or_404(FeeType, pk=pk)
    if request.method == "POST":
        fee.delete()
        messages.success(request, "Fee type deleted successfully.")
        return redirect("fee_types")
    return render(request, "finance/delete_fee_type.html", {"fee": fee})




def bulk_create_fee_records(request):
    if request.method == "POST":
        form = BulkFeeCreationForm(request.POST)
        if form.is_valid():
            session = form.cleaned_data["session"]
            term = form.cleaned_data["term"]
            fee_type = form.cleaned_data["fee_type"]
            total_amount = form.cleaned_data["total_amount"]

            students = Student.objects.all()
            created_count = 0
            skipped_count = 0

            for student in students:
                obj, created = StudentFeeRecord.objects.get_or_create(
                    student=student,
                    session=session,
                    term=term,
                    fee_type=fee_type,
                    defaults={
                        "total_amount": total_amount,
                        "amount_paid": 0,
                        "balance": total_amount,
                    },
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

            messages.success(request, f"✅ {created_count} records created, {skipped_count} skipped (already exist).")
            return redirect("manage_fees")
    else:
        form = BulkFeeCreationForm()

    return render(request, "finance/bulk_create_fee_records.html", {"form": form})


from .forms import InvoiceForm

@login_required
def edit_invoice(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            form.save()
            messages.success(request, "Invoice updated successfully!")
            return redirect('manage_invoices')
    else:
        form = InvoiceForm(instance=invoice)
    return render(request, 'finance/edit_invoice.html', {'form': form, 'invoice': invoice})


@login_required
def delete_invoice(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    invoice.delete()
    messages.success(request, "Invoice deleted successfully!")
    return redirect('manage_invoices')
