from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),

    path('about/', views.about_view, name='about'),
    path('admissions/', views.admissions_view, name='admissions'),
    path('academics/', views.academics_view, name='academics'),
    path('contact/', views.contact_view, name='contact'),
]
