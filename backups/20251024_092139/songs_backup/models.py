from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError

User = get_user_model()

LANGUAGE_CHOICES = [
    ("tamil", "Tamil"),
    ("telugu", "Telugu"),
    ("english", "English"),
]

CATEGORY_CHOICES = [
    ("ayyappa", "Ayyappa"),
    ("siva", "Siva"),
    ("amman", "Amman"),
    ("murugan", "Murugan"),
    ("venkateswara", "Venkateswara"),
    ("others", "Others"),
]


class UserProfile(models.Model):
    """Extended user profile for region and preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    language_preference = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default="tamil")
    region = models.CharField(max_length=100, blank=True, help_text="User's region/state")
    city = models.CharField(max_length=100, blank=True)
    contact = models.CharField(max_length=20, blank=True, help_text="Mobile number")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.region}"


class SongAccess(models.Model):
    """Track which users can access which songs"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='song_access')
    song = models.ForeignKey('Song', on_delete=models.CASCADE, related_name='user_access')
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='granted_access')
    granted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'song']
        indexes = [
            models.Index(fields=['user', 'song']),
        ]
    
    def __str__(self):
        return f"{self.user.username} → {self.song.display_title}"


class AccessRequest(models.Model):
    """Users can request access to songs"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='access_requests')
    song = models.ForeignKey('Song', on_delete=models.CASCADE, related_name='access_requests')
    message = models.TextField(blank=True, help_text="Optional message to admin")
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied')
    ], default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')
    
    class Meta:
        unique_together = ['user', 'song']
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.user.username} → {self.song.display_title} [{self.status}]"


class AudioFile(models.Model):
    """Stores audio files/URLs to avoid duplication across songs"""
    source_type = models.CharField(max_length=20, choices=[
        ("file", "Uploaded File"),
        ("youtube", "YouTube URL"),
        ("url", "External URL")
    ], default="file")
    
    youtube_url = models.URLField(max_length=500, blank=True, null=True, unique=True)
    audio_file = models.FileField(upload_to="audio_files/", blank=True, null=True)
    
    title = models.CharField(max_length=255, blank=True)
    duration = models.IntegerField(blank=True, null=True, help_text="Duration in seconds")
    file_size = models.BigIntegerField(blank=True, null=True, help_text="File size in bytes")
    
    created_at = models.DateTimeField(auto_now_add=True)
    reference_count = models.IntegerField(default=0, help_text="Number of songs using this audio")
    
    class Meta:
        indexes = [
            models.Index(fields=['youtube_url']),
            models.Index(fields=['source_type']),
        ]
    
    def __str__(self):
        if self.youtube_url:
            return f"YouTube: {self.title or self.youtube_url[:50]}"
        return f"File: {self.title or self.audio_file.name if self.audio_file else 'Unknown'}"
    
    def get_audio_url(self):
        """Returns the audio URL regardless of source"""
        if self.audio_file:
            return self.audio_file.url
        return None
    
    def increment_reference(self):
        """Increment reference count when song uses this audio"""
        self.reference_count += 1
        self.save(update_fields=['reference_count'])
    
    def decrement_reference(self):
        """Decrement reference count when song stops using this audio"""
        if self.reference_count > 0:
            self.reference_count -= 1
            self.save(update_fields=['reference_count'])


class Song(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="songs")
    
    # Multilingual titles
    title_ta = models.CharField(max_length=255, blank=True, verbose_name="Tamil Title")
    title_te = models.CharField(max_length=255, blank=True, verbose_name="Telugu Title")
    title_en = models.CharField(max_length=255, blank=True, verbose_name="English Title")
    
    # Primary language for default display
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default="tamil")
    
    # Category for filtering and organization
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="others", help_text="Deity/Theme category")
    
    # Multilingual lyrics
    lyrics_ta = models.TextField(blank=True, verbose_name="Tamil Lyrics")
    lyrics_te = models.TextField(blank=True, verbose_name="Telugu Lyrics")
    lyrics_en = models.TextField(blank=True, verbose_name="English Lyrics")
    
    # Audio reference (deduplicated)
    audio_file = models.ForeignKey(AudioFile, on_delete=models.SET_NULL, null=True, blank=True, related_name="songs")
    
    # Legacy field for backward compatibility (will be migrated to audio_file)
    audio = models.FileField(upload_to="audio_files/", blank=True, null=True)
    
    cover_image = models.ImageField(upload_to="covers/", blank=True, null=True)
    uploaded_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Metadata
    is_favorite = models.BooleanField(default=False, help_text="Mark as favorite for quick access")
    play_count = models.IntegerField(default=0, help_text="Number of times played")
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['language']),
            models.Index(fields=['is_favorite']),
            models.Index(fields=['-uploaded_at']),
        ]
    
    def __str__(self):
        return self.get_title()
    
    @property
    def display_title(self):
        """Property for displaying title with multilingual fallback"""
        return self.title_ta or self.title_te or self.title_en or "Untitled"
    
    def get_title(self, language=None):
        """Get title in specified language, fallback to primary language"""
        if not language:
            language = self.language
        
        if language == "tamil" and self.title_ta:
            return self.title_ta
        elif language == "telugu" and self.title_te:
            return self.title_te
        elif language == "english" and self.title_en:
            return self.title_en
        
        # Fallback to any available title
        return self.title_ta or self.title_te or self.title_en or "Untitled Song"
    
    def get_lyrics(self, language=None):
        """Get lyrics in specified language"""
        if not language:
            language = self.language
        
        if language == "tamil":
            return self.lyrics_ta
        elif language == "telugu":
            return self.lyrics_te
        elif language == "english":
            return self.lyrics_en
        return ""
    
    def has_audio(self):
        """Check if song has audio (new or legacy)"""
        return bool(self.audio_file or self.audio)
    has_audio.boolean = True
    has_audio.short_description = "Audio?"
    
    def get_audio_url(self):
        """Get audio URL from AudioFile or legacy audio field"""
        if self.audio_file:
            return self.audio_file.get_audio_url()
        elif self.audio:
            return self.audio.url
        return None
    
    def available_languages(self):
        """Return list of languages that have content"""
        langs = []
        if self.title_ta or self.lyrics_ta:
            langs.append(("tamil", "Tamil"))
        if self.title_te or self.lyrics_te:
            langs.append(("telugu", "Telugu"))
        if self.title_en or self.lyrics_en:
            langs.append(("english", "English"))
        return langs
    
    def missing_languages(self):
        """Return list of languages that don't have content yet"""
        available = [lang[0] for lang in self.available_languages()]
        return [(code, name) for code, name in LANGUAGE_CHOICES if code not in available]
    
    def save(self, *args, **kwargs):
        # Update audio_file reference count if changed
        if self.pk:
            old_instance = Song.objects.filter(pk=self.pk).first()
            if old_instance and old_instance.audio_file != self.audio_file:
                if old_instance.audio_file:
                    old_instance.audio_file.decrement_reference()
                if self.audio_file:
                    self.audio_file.increment_reference()
        elif self.audio_file:
            self.audio_file.increment_reference()
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Decrement reference count when deleting song
        if self.audio_file:
            self.audio_file.decrement_reference()
        super().delete(*args, **kwargs)


class Astotharam(models.Model):
    """108 names/verses of deities"""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="astotharams")
    
    # Multilingual titles
    title_ta = models.CharField(max_length=255, blank=True, verbose_name="Tamil Title")
    title_te = models.CharField(max_length=255, blank=True, verbose_name="Telugu Title")
    title_en = models.CharField(max_length=255, blank=True, verbose_name="English Title")
    
    # Multilingual content
    content_ta = models.TextField(blank=True, verbose_name="Tamil Content")
    content_te = models.TextField(blank=True, verbose_name="Telugu Content")
    content_en = models.TextField(blank=True, verbose_name="English Content")
    
    # Metadata
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default="tamil")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="others")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Astotharam"
        verbose_name_plural = "Astotharams"
    
    def __str__(self):
        return self.get_title()
    
    @property
    def display_title(self):
        return self.title_ta or self.title_te or self.title_en or "Untitled"
    
    def get_title(self, language=None):
        if not language:
            language = self.language
        if language == "tamil" and self.title_ta:
            return self.title_ta
        elif language == "telugu" and self.title_te:
            return self.title_te
        elif language == "english" and self.title_en:
            return self.title_en
        return self.title_ta or self.title_te or self.title_en or "Untitled"
    
    def get_content(self, language=None):
        if not language:
            language = self.language
        if language == "tamil":
            return self.content_ta
        elif language == "telugu":
            return self.content_te
        elif language == "english":
            return self.content_en
        return ""


class Saranaghosha(models.Model):
    """Devotional chants and mantras"""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saranagoshas")
    
    # Multilingual titles
    title_ta = models.CharField(max_length=255, blank=True, verbose_name="Tamil Title")
    title_te = models.CharField(max_length=255, blank=True, verbose_name="Telugu Title")
    title_en = models.CharField(max_length=255, blank=True, verbose_name="English Title")
    
    # Multilingual content
    content_ta = models.TextField(blank=True, verbose_name="Tamil Content")
    content_te = models.TextField(blank=True, verbose_name="Telugu Content")
    content_en = models.TextField(blank=True, verbose_name="English Content")
    
    # Metadata
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default="tamil")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="others")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Saranaghosha"
        verbose_name_plural = "Saranagoshas"
    
    def __str__(self):
        return self.get_title()
    
    @property
    def display_title(self):
        return self.title_ta or self.title_te or self.title_en or "Untitled"
    
    def get_title(self, language=None):
        if not language:
            language = self.language
        if language == "tamil" and self.title_ta:
            return self.title_ta
        elif language == "telugu" and self.title_te:
            return self.title_te
        elif language == "english" and self.title_en:
            return self.title_en
        return self.title_ta or self.title_te or self.title_en or "Untitled"
    
    def get_content(self, language=None):
        if not language:
            language = self.language
        if language == "tamil":
            return self.content_ta
        elif language == "telugu":
            return self.content_te
        elif language == "english":
            return self.content_en
        return ""


class AppSettings(models.Model):
    """Global app settings for customization"""
    # Categories management (JSON field for dynamic categories)
    custom_categories = models.JSONField(default=list, blank=True, help_text="Custom deity categories")
    
    # Theme settings
    primary_color = models.CharField(max_length=7, default="#d97706", help_text="Primary theme color (hex)")
    secondary_color = models.CharField(max_length=7, default="#f59e0b", help_text="Secondary theme color (hex)")
    
    # Banner/Header text
    site_title = models.CharField(max_length=100, default="Swamiye Saranam Ayyappa")
    site_subtitle = models.CharField(max_length=200, default="Devotional Songs Collection", blank=True)
    
    # Feature toggles
    enable_categories = models.BooleanField(default=True)
    enable_astotharam = models.BooleanField(default=True)
    enable_saranaghosha = models.BooleanField(default=True)
    
    # Meta
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "App Settings"
        verbose_name_plural = "App Settings"
    
    def __str__(self):
        return f"App Settings (Updated: {self.updated_at.strftime('%Y-%m-%d')})"
    
    @classmethod
    def get_settings(cls):
        """Get or create singleton settings instance"""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
