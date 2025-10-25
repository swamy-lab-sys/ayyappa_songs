# ============================================================================
# ENHANCED MODELS FOR SINGERSITE
# Add these to songs/models.py
# ============================================================================

from django.db import models
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
import json

User = get_user_model()


class SiteConfig(models.Model):
    """
    Enhanced singleton configuration model with caching.
    Replaces AppSettings with better structure and performance.
    """
    
    # Site Identity
    site_title = models.CharField(max_length=100, default="Swamiye Saranam Ayyappa")
    site_subtitle = models.CharField(max_length=200, default="Devotional Songs Collection", blank=True)
    site_logo = models.ImageField(upload_to="config/", blank=True, null=True)
    
    # Theme Colors
    primary_color = models.CharField(max_length=7, default="#d97706", help_text="Hex color code")
    secondary_color = models.CharField(max_length=7, default="#f59e0b", help_text="Hex color code")
    accent_color = models.CharField(max_length=7, default="#9333ea", help_text="Hex color code")
    
    # Feature Toggles (Module Control)
    enable_categories = models.BooleanField(default=True, help_text="Show category filters")
    enable_astotharam = models.BooleanField(default=True, help_text="Enable 108 names section")
    enable_saranaghosha = models.BooleanField(default=True, help_text="Enable mantras section")
    enable_dark_mode = models.BooleanField(default=True, help_text="Allow users to toggle dark mode")
    enable_pwa = models.BooleanField(default=True, help_text="Enable Progressive Web App features")
    
    # Access Control
    require_approval_for_songs = models.BooleanField(
        default=False,
        help_text="Require admin approval for new song uploads"
    )
    allow_guest_browsing = models.BooleanField(
        default=True,
        help_text="Allow non-authenticated users to browse content"
    )
    
    # Pagination Settings
    songs_per_page = models.IntegerField(default=12, help_text="Songs displayed per page")
    users_per_page = models.IntegerField(default=20, help_text="Users displayed per page in admin")
    
    # Custom Categories (JSON field for dynamic deity categories)
    custom_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="Additional custom deity categories beyond defaults"
    )
    
    # Meta
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="config_updates"
    )
    
    class Meta:
        verbose_name = "Site Configuration"
        verbose_name_plural = "Site Configuration"
    
    def __str__(self):
        return f"Site Config (Updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')})"
    
    @classmethod
    def get_config(cls, use_cache=True):
        """
        Get or create singleton configuration with caching.
        Cache TTL: 15 minutes
        """
        cache_key = "site_config_singleton"
        
        if use_cache:
            config = cache.get(cache_key)
            if config:
                return config
        
        config, created = cls.objects.get_or_create(pk=1)
        
        if use_cache:
            cache.set(cache_key, config, 900)  # 15 minutes
        
        return config
    
    def save(self, *args, **kwargs):
        """Override save to invalidate cache"""
        super().save(*args, **kwargs)
        cache.delete("site_config_singleton")
    
    def get_navigation_modules(self):
        """Returns list of enabled navigation modules"""
        modules = []
        
        modules.append({"name": "Songs", "url": "song_list", "icon": "fa-music"})
        
        if self.enable_astotharam:
            modules.append({"name": "Astotharam", "url": "astotharam_list", "icon": "fa-om"})
        
        if self.enable_saranaghosha:
            modules.append({"name": "Saranaghosha", "url": "saranaghosha_list", "icon": "fa-hands-praying"})
        
        return modules


class ActivityLog(models.Model):
    """
    Comprehensive activity logging for admin actions.
    Tracks who did what, when, and on which object.
    """
    
    ACTION_TYPES = [
        ('user_created', 'User Created'),
        ('user_updated', 'User Updated'),
        ('user_deleted', 'User Deleted'),
        ('user_promoted', 'User Promoted to Admin'),
        ('user_demoted', 'User Demoted from Admin'),
        
        ('song_created', 'Song Created'),
        ('song_updated', 'Song Updated'),
        ('song_deleted', 'Song Deleted'),
        
        ('access_granted', 'Access Granted'),
        ('access_revoked', 'Access Revoked'),
        ('access_request_approved', 'Access Request Approved'),
        ('access_request_denied', 'Access Request Denied'),
        
        ('settings_updated', 'Settings Updated'),
        
        ('astotharam_created', 'Astotharam Created'),
        ('astotharam_updated', 'Astotharam Updated'),
        ('astotharam_deleted', 'Astotharam Deleted'),
        
        ('saranaghosha_created', 'Saranaghosha Created'),
        ('saranaghosha_updated', 'Saranaghosha Updated'),
        ('saranaghosha_deleted', 'Saranaghosha Deleted'),
    ]
    
    # Who performed the action
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="activity_logs",
        help_text="User who performed the action"
    )
    
    # What action was performed
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    action_description = models.CharField(max_length=255, help_text="Human-readable description")
    
    # When it happened
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    # On which object (generic tracking)
    object_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of object affected (User, Song, etc.)"
    )
    object_id = models.IntegerField(null=True, blank=True, help_text="ID of affected object")
    object_repr = models.CharField(
        max_length=255,
        blank=True,
        help_text="String representation of affected object"
    )
    
    # Additional context (JSON for flexibility)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context (old values, IP address, etc.)"
    )
    
    # IP Address tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['actor', '-timestamp']),
            models.Index(fields=['action_type', '-timestamp']),
        ]
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
    
    def __str__(self):
        actor_name = self.actor.username if self.actor else "System"
        return f"{actor_name} - {self.get_action_type_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def log_activity(cls, actor, action_type, description, object_type=None, 
                     object_id=None, object_repr=None, metadata=None, ip_address=None):
        """
        Convenience method to create activity logs.
        
        Usage:
            ActivityLog.log_activity(
                actor=request.user,
                action_type='user_created',
                description=f"Created user {new_user.username}",
                object_type='User',
                object_id=new_user.id,
                object_repr=str(new_user),
                metadata={'email': new_user.email, 'role': 'standard'},
                ip_address=get_client_ip(request)
            )
        """
        return cls.objects.create(
            actor=actor,
            action_type=action_type,
            action_description=description,
            object_type=object_type,
            object_id=object_id,
            object_repr=object_repr,
            metadata=metadata or {},
            ip_address=ip_address
        )


# ============================================================================
# HELPER FUNCTION: Get Client IP Address
# ============================================================================

def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ============================================================================
# ADD TO EXISTING MODELS: Indexing Improvements
# ============================================================================

"""
Add these Meta changes to existing models:

class UserProfile(models.Model):
    # ... existing fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['region']),  # ← ADD THIS
            models.Index(fields=['language_preference']),  # ← ADD THIS
        ]


class AccessRequest(models.Model):
    # ... existing fields ...
    
    class Meta:
        unique_together = ['user', 'song']
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', '-requested_at']),  # ← ADD THIS
            models.Index(fields=['user', 'status']),  # ← ADD THIS
        ]
"""
