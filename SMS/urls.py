from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),

    # 🌐 Public landing page
    path('', include('core.urls')),

    # 🔐 Authentication
    path('accounts/', include('accounts.urls')),

    # 📚 SMS Modules
    path('finance/', include('finance.urls')),
    path('academics/', include('academics.urls')),
    path('results/', include('results.urls')),
    path('communications/', include('communications.urls')),
    path('attendance/', include('attendance.urls')),
    path('reportcard/', include('reportcard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
