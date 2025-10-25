from rest_framework import routers
from .api_views import SongViewSet, AudioFileViewSet
from django.urls import path, include

router = routers.DefaultRouter()
router.register('songs', SongViewSet, basename='song')
router.register('audio-files', AudioFileViewSet, basename='audiofile')

urlpatterns = [
    path('', include(router.urls)),
]
