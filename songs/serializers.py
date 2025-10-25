from rest_framework import serializers
from .models import Song, AudioFile


class AudioFileSerializer(serializers.ModelSerializer):
    audio_url = serializers.SerializerMethodField()
    
    class Meta:
        model = AudioFile
        fields = [
            "id",
            "source_type",
            "youtube_url",
            "title",
            "duration",
            "audio_url",
            "reference_count",
            "created_at",
        ]
        read_only_fields = ["reference_count", "created_at"]
    
    def get_audio_url(self, obj):
        request = self.context.get("request")
        url = obj.get_audio_url()
        if url and request:
            return request.build_absolute_uri(url)
        return url


class SongSerializer(serializers.ModelSerializer):
    audio_url = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    available_languages = serializers.SerializerMethodField()
    display_title = serializers.SerializerMethodField()

    class Meta:
        model = Song
        fields = [
            "id",
            "display_title",
            "title_ta",
            "title_te",
            "title_en",
            "language",
            "lyrics_ta",
            "lyrics_te",
            "lyrics_en",
            "audio_url",
            "cover_image_url",
            "is_favorite",
            "play_count",
            "uploaded_at",
            "updated_at",
            "owner_username",
            "available_languages",
        ]

    def get_display_title(self, obj):
        return obj.get_title()
    
    def get_audio_url(self, obj):
        request = self.context.get("request")
        url = obj.get_audio_url()
        if url and request:
            return request.build_absolute_uri(url)
        return url

    def get_cover_image_url(self, obj):
        request = self.context.get("request")
        if obj.cover_image and request:
            return request.build_absolute_uri(obj.cover_image.url)
        elif obj.cover_image:
            return obj.cover_image.url
        return None
    
    def get_available_languages(self, obj):
        return [{"code": code, "name": name} for code, name in obj.available_languages()]
