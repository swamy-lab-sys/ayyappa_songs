from django.contrib import admin
from .models import Song, AudioFile, UserProfile, SongAccess, AccessRequest
from django.http import HttpResponse
import csv


@admin.register(AudioFile)
class AudioFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'source_type', 'reference_count', 'created_at')
    list_filter = ('source_type', 'created_at')
    search_fields = ('title', 'youtube_url')
    readonly_fields = ('reference_count', 'created_at', 'file_size')
    
    fieldsets = (
        ('Audio Information', {
            'fields': ('title', 'source_type', 'youtube_url', 'audio_file')
        }),
        ('Metadata', {
            'fields': ('duration', 'file_size', 'reference_count', 'created_at')
        }),
    )


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ("get_display_title", "language", "owner", "uploaded_at", "has_audio", "is_favorite")
    list_filter = ("language", "is_favorite", "uploaded_at")
    search_fields = ("title_ta", "title_te", "title_en", "lyrics_ta", "lyrics_te", "lyrics_en", "owner__username")
    readonly_fields = ('uploaded_at', 'updated_at', 'play_count')
    list_editable = ('is_favorite',)
    actions = ["export_as_csv"]
    
    fieldsets = (
        ('Song Information', {
            'fields': ('owner', 'language')
        }),
        ('Multilingual Titles', {
            'fields': ('title_ta', 'title_te', 'title_en')
        }),
        ('Multilingual Lyrics', {
            'fields': ('lyrics_ta', 'lyrics_te', 'lyrics_en'),
            'classes': ('collapse',)
        }),
        ('Media', {
            'fields': ('audio_file', 'audio', 'cover_image')
        }),
        ('Metadata', {
            'fields': ('is_favorite', 'play_count', 'uploaded_at', 'updated_at')
        }),
    )
    
    def get_display_title(self, obj):
        return obj.get_title()
    get_display_title.short_description = 'Title'

    def export_as_csv(self, request, queryset):
        field_names = [
            "id", "title_ta", "title_te", "title_en", "language", "owner", "uploaded_at",
            "lyrics_ta", "lyrics_te", "lyrics_en"
        ]
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=songs_export.csv"
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([
                getattr(obj, f) if f != "owner" else obj.owner.username
                for f in field_names
            ])
        return response

    export_as_csv.short_description = "Export selected songs as CSV"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'language_preference', 'region', 'city', 'created_at')
    list_filter = ('language_preference', 'region')
    search_fields = ('user__username', 'user__email', 'region', 'city', 'contact')
    readonly_fields = ('created_at',)


@admin.register(SongAccess)
class SongAccessAdmin(admin.ModelAdmin):
    list_display = ('user', 'song', 'granted_by', 'granted_at')
    list_filter = ('granted_at', 'granted_by')
    search_fields = ('user__username', 'song__title_ta', 'song__title_te', 'song__title_en')
    readonly_fields = ('granted_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'song', 'granted_by')


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'song', 'status', 'requested_at', 'reviewed_by')
    list_filter = ('status', 'requested_at', 'reviewed_at')
    search_fields = ('user__username', 'song__title_ta', 'song__title_te', 'song__title_en', 'message')
    readonly_fields = ('requested_at', 'reviewed_at')
    actions = ['approve_requests', 'deny_requests']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'song', 'reviewed_by')
    
    def approve_requests(self, request, queryset):
        for access_request in queryset.filter(status='pending'):
            SongAccess.objects.get_or_create(
                user=access_request.user,
                song=access_request.song,
                defaults={'granted_by': request.user}
            )
            access_request.status = 'approved'
            access_request.reviewed_by = request.user
            from django.utils import timezone
            access_request.reviewed_at = timezone.now()
            access_request.save()
        self.message_user(request, f"{queryset.count()} requests approved.")
    approve_requests.short_description = "Approve selected access requests"
    
    def deny_requests(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status='pending').update(
            status='denied',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f"{queryset.count()} requests denied.")
    deny_requests.short_description = "Deny selected access requests"
