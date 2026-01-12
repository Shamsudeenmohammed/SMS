from core.models import SiteUpdate
from accounts.models import Student, Teacher, Parent, CustomUser
from django.shortcuts import render
from django.core.mail import send_mail
from django.conf import settings
from .forms import ContactForm

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


from django.shortcuts import render

def about_view(request):
    return render(request, 'core/about.html')

def admissions_view(request):
    return render(request, 'core/admissions.html')

def academics_view(request):
    return render(request, 'core/academics.html')

def contact_view(request):
    return render(request, 'core/contact.html')



def contact_view(request):
    success = False

    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']

            full_message = f"""
            New Contact Message

            Name: {name}
            Email: {email}

            Message:
            {message}
            """

            send_mail(
                subject=f"[School Website] {subject}",
                message=full_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.DEFAULT_FROM_EMAIL],
                fail_silently=False,
            )

            success = True
            form = ContactForm()  # Clear form after success
    else:
        form = ContactForm()

    return render(request, 'core/contact.html', {
        'form': form,
        'success': success
    })
