from core.models import SiteUpdate
from accounts.models import Student, Teacher, Parent, CustomUser
from django.shortcuts import render

def home(request):
    latest_update = SiteUpdate.objects.filter(is_active=True).first()

    context = {
        "latest_update": latest_update,
        "total_students": Student.objects.filter(is_active=True).count(),
        "total_teachers": Teacher.objects.count(),
        "total_parents": Parent.objects.count(),
        "total_users": CustomUser.objects.count(),
    }
    return render(request, "core/home.html", context)
