from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings

urlpatterns = [
    path('getout/', admin.site.urls),

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

# Serve media files (static() only works when DEBUG=True, so use serve() directly)
urlpatterns += [
    re_path(r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'), serve, {'document_root': settings.MEDIA_ROOT}),
]
