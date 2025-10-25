from rest_framework import viewsets, permissions, filters
from .models import Song, AudioFile
from .serializers import SongSerializer, AudioFileSerializer


class AudioFileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing AudioFile instances.
    Read-only to prevent external manipulation.
    """
    queryset = AudioFile.objects.all().order_by("-created_at")
    serializer_class = AudioFileSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class SongViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Song CRUD operations with search and filtering.
    """
    queryset = Song.objects.select_related('owner', 'audio_file').all()
    serializer_class = SongSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title_ta', 'title_te', 'title_en', 'lyrics_ta', 'lyrics_te', 'lyrics_en']
    ordering_fields = ['uploaded_at', 'play_count']
    ordering = ['-uploaded_at']

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by language
        language = self.request.query_params.get('language', None)
        if language:
            queryset = queryset.filter(language=language)
        
        # Filter by favorites
        favorites = self.request.query_params.get('favorites', None)
        if favorites == '1' or favorites == 'true':
            queryset = queryset.filter(is_favorite=True)
        
        return queryset
