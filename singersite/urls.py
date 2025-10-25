from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Songs app routes (includes custom /admin/* routes)
    path('', include('songs.urls')),
    
    # Django built-in admin (moved to /djangoadmin/ to avoid conflicts)
    path('djangoadmin/', admin.site.urls),
    
    # API routes
    path('api/', include('songs.api_urls')),
    
    # PWA Offline Page
    path('offline/', TemplateView.as_view(template_name='songs/offline.html'), name='offline'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
