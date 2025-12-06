from django.urls import path
from . import views

urlpatterns = [
    path("select/", views.select_report_options, name="select_report_options"),
    path(
        "generate/<int:student_id>/<int:session_id>/<str:term>/",
        views.generate_report,
        name="generate_report"
    ),
]
