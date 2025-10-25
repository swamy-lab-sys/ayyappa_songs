# ============================================================================
# ENHANCED VIEWS WITH HTMX SUPPORT & QUERY OPTIMIZATION
# Add these to songs/views.py or create songs/views_admin.py
# ============================================================================

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Prefetch
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from functools import wraps

from .models import (
    Song, UserProfile, SongAccess, AccessRequest, 
    ActivityLog, SiteConfig, get_client_ip
)

User = get_user_model()


# ============================================================================
# PERMISSION DECORATORS
# ============================================================================

def admin_required(view_func):
    """
    Decorator to require staff/superuser access.
    Cleaner than repeated if checks in views.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access this page.")
            return redirect('login')
        
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "Admin access required.")
            return redirect('song_list')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


# ============================================================================
# OPTIMIZED USER DASHBOARD WITH HTMX LIVE SEARCH
# ============================================================================

@login_required
@admin_required
@require_http_methods(["GET"])
def admin_users_dashboard_v2(request):
    """
    Optimized user dashboard with:
    - Query optimization (select_related/prefetch_related)
    - HTMX live search support
    - Mobile-responsive design
    - Real-time filtering
    """
    
    # Get filter parameters
    search = request.GET.get('search', '').strip()
    filter_region = request.GET.get('region', '').strip()
    filter_language = request.GET.get('language', '').strip()
    filter_role = request.GET.get('role', '').strip()
    page_number = request.GET.get('page', 1)
    
    # ✅ OPTIMIZED QUERY: Use select_related to avoid N+1
    users = User.objects.select_related('profile').annotate(
        song_count=Count('songs'),
        access_count=Count('song_access')
    )
    
    # Search filter (username, email, region)
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(profile__region__icontains=search) |
            Q(profile__city__icontains=search)
        )
    
    # Region filter
    if filter_region:
        users = users.filter(profile__region__iexact=filter_region)
    
    # Language filter
    if filter_language:
        users = users.filter(profile__language_preference=filter_language)
    
    # Role filter
    if filter_role == 'admin':
        users = users.filter(is_staff=True)
    elif filter_role == 'user':
        users = users.filter(is_staff=False)
    
    # Order by latest
    users = users.order_by('-date_joined')
    
    # Get unique regions for filter dropdown
    regions = UserProfile.objects.exclude(
        region__exact=''
    ).values_list('region', flat=True).distinct().order_by('region')
    
    # Statistics
    stats = {
        'total_users': User.objects.count(),
        'total_staff': User.objects.filter(is_staff=True).count(),
        'total_regular': User.objects.filter(is_staff=False).count(),
        'total_with_songs': User.objects.annotate(
            song_count=Count('songs')
        ).filter(song_count__gt=0).count(),
    }
    
    # Pagination
    config = SiteConfig.get_config()
    paginator = Paginator(users, config.users_per_page)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'users': page_obj,  # For template compatibility
        'stats': stats,
        'regions': regions,
        'search': search,
        'filter_region': filter_region,
        'filter_language': filter_language,
        'filter_role': filter_role,
    }
    
    # ✅ HTMX SUPPORT: Return partial template for AJAX requests
    if request.headers.get('HX-Request'):
        return render(request, 'songs/partials/user_table_rows.html', context)
    
    return render(request, 'songs/admin_users_dashboard_v2.html', context)


# ============================================================================
# HTMX-POWERED LIVE SEARCH ENDPOINT
# ============================================================================

@login_required
@admin_required
@require_http_methods(["GET"])
def users_live_search(request):
    """
    Dedicated endpoint for HTMX live search.
    Returns only the user table rows for instant updates.
    """
    search = request.GET.get('q', '').strip()
    
    if len(search) < 2:  # Minimum 2 characters
        return HttpResponse('<tr><td colspan="6" class="p-4 text-center text-gray-500">Type at least 2 characters to search...</td></tr>')
    
    users = User.objects.select_related('profile').annotate(
        song_count=Count('songs')
    ).filter(
        Q(username__icontains=search) |
        Q(email__icontains=search) |
        Q(profile__region__icontains=search)
    )[:10]  # Limit to 10 results for performance
    
    return render(request, 'songs/partials/user_search_results.html', {'users': users})


# ============================================================================
# ADMIN SETTINGS WITH HTMX FORM SUBMISSION
# ============================================================================

@login_required
@admin_required
@csrf_protect
def admin_settings_v2(request):
    """
    Enhanced settings page with:
    - HTMX form submission (no page reload)
    - Real-time color preview
    - Activity logging
    - Toast notifications
    """
    from .models import CATEGORY_CHOICES
    
    config = SiteConfig.get_config()
    
    if request.method == "POST":
        # Update configuration
        old_values = {
            'site_title': config.site_title,
            'primary_color': config.primary_color,
            'enable_astotharam': config.enable_astotharam,
        }
        
        config.site_title = request.POST.get('site_title', config.site_title)
        config.site_subtitle = request.POST.get('site_subtitle', config.site_subtitle)
        config.primary_color = request.POST.get('primary_color', config.primary_color)
        config.secondary_color = request.POST.get('secondary_color', config.secondary_color)
        config.accent_color = request.POST.get('accent_color', config.accent_color)
        
        # Feature toggles
        config.enable_categories = request.POST.get('enable_categories') == 'on'
        config.enable_astotharam = request.POST.get('enable_astotharam') == 'on'
        config.enable_saranaghosha = request.POST.get('enable_saranaghosha') == 'on'
        config.enable_dark_mode = request.POST.get('enable_dark_mode') == 'on'
        
        # Pagination settings
        try:
            config.songs_per_page = int(request.POST.get('songs_per_page', 12))
            config.users_per_page = int(request.POST.get('users_per_page', 20))
        except ValueError:
            pass
        
        config.updated_by = request.user
        config.save()
        
        # ✅ LOG ACTIVITY
        ActivityLog.log_activity(
            actor=request.user,
            action_type='settings_updated',
            description=f"{request.user.username} updated site settings",
            object_type='SiteConfig',
            object_id=config.id,
            object_repr=str(config),
            metadata={
                'old_values': old_values,
                'new_values': {
                    'site_title': config.site_title,
                    'primary_color': config.primary_color,
                    'enable_astotharam': config.enable_astotharam,
                }
            },
            ip_address=get_client_ip(request)
        )
        
        messages.success(request, "✅ Settings saved successfully!")
        
        # ✅ HTMX RESPONSE: Return success message
        if request.headers.get('HX-Request'):
            return HttpResponse(
                '<div class="p-4 bg-green-100 border border-green-300 text-green-800 rounded-lg">'
                '<i class="fa-solid fa-circle-check mr-2"></i>Settings saved successfully!'
                '</div>',
                headers={'HX-Trigger': 'settingsSaved'}
            )
        
        return redirect('admin_settings_v2')
    
    context = {
        'config': config,
        'categories': CATEGORY_CHOICES,
    }
    
    return render(request, 'songs/admin_settings_v2.html', context)


# ============================================================================
# ACTIVITY LOG VIEWER
# ============================================================================

@login_required
@admin_required
def admin_activity_log(request):
    """
    View for browsing admin activity logs.
    Filterable by date range, action type, and actor.
    """
    from datetime import timedelta
    from django.utils import timezone
    
    # Filters
    days = int(request.GET.get('days', 7))  # Last 7 days by default
    action_type = request.GET.get('action_type', '')
    actor_id = request.GET.get('actor', '')
    
    # Calculate date threshold
    date_threshold = timezone.now() - timedelta(days=days)
    
    # Query logs
    logs = ActivityLog.objects.filter(
        timestamp__gte=date_threshold
    ).select_related('actor').order_by('-timestamp')
    
    if action_type:
        logs = logs.filter(action_type=action_type)
    
    if actor_id:
        logs = logs.filter(actor_id=actor_id)
    
    # Pagination
    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    
    # Get available actors (for filter dropdown)
    actors = User.objects.filter(
        activity_logs__isnull=False
    ).distinct().order_by('username')
    
    context = {
        'page_obj': page_obj,
        'days': days,
        'action_type': action_type,
        'actor_id': actor_id,
        'actors': actors,
        'action_types': ActivityLog.ACTION_TYPES,
    }
    
    return render(request, 'songs/admin_activity_log.html', context)


# ============================================================================
# USER PROMOTION/DEMOTION WITH ACTIVITY LOGGING
# ============================================================================

@login_required
@admin_required
@require_http_methods(["POST"])
def admin_toggle_user_role(request, user_id):
    """
    Toggle user between admin and regular user.
    Logs the activity for audit trail.
    """
    target_user = get_object_or_404(User, id=user_id)
    
    # Prevent self-demotion
    if target_user == request.user:
        messages.error(request, "You cannot change your own role.")
        return redirect('admin_users_dashboard_v2')
    
    # Prevent demotion of superusers
    if target_user.is_superuser and not request.user.is_superuser:
        messages.error(request, "You cannot modify a superuser's role.")
        return redirect('admin_users_dashboard_v2')
    
    # Toggle staff status
    if target_user.is_staff:
        target_user.is_staff = False
        action_type = 'user_demoted'
        action_msg = f"Demoted {target_user.username} from admin to regular user"
        messages.success(request, f"✅ {target_user.username} demoted to regular user.")
    else:
        target_user.is_staff = True
        action_type = 'user_promoted'
        action_msg = f"Promoted {target_user.username} to admin"
        messages.success(request, f"✅ {target_user.username} promoted to admin.")
    
    target_user.save()
    
    # Log activity
    ActivityLog.log_activity(
        actor=request.user,
        action_type=action_type,
        description=action_msg,
        object_type='User',
        object_id=target_user.id,
        object_repr=target_user.username,
        metadata={'new_role': 'admin' if target_user.is_staff else 'user'},
        ip_address=get_client_ip(request)
    )
    
    return redirect('admin_users_dashboard_v2')


# ============================================================================
# HTMX PARTIAL: Song List with Instant Search
# ============================================================================

@login_required
@require_http_methods(["GET"])
def songs_htmx_search(request):
    """
    HTMX endpoint for instant song search.
    Returns only the song cards for seamless updates.
    """
    from .models import CATEGORY_CHOICES
    
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    language = request.GET.get('language', '')
    
    songs = Song.objects.select_related('owner', 'audio_file')
    
    # Apply filters
    if q:
        songs = songs.filter(
            Q(title_ta__icontains=q) |
            Q(title_te__icontains=q) |
            Q(title_en__icontains=q) |
            Q(lyrics_ta__icontains=q) |
            Q(lyrics_te__icontains=q) |
            Q(lyrics_en__icontains=q)
        )
    
    if category:
        songs = songs.filter(category=category)
    
    if language:
        songs = songs.filter(language=language)
    
    # Pagination
    config = SiteConfig.get_config()
    paginator = Paginator(songs, config.songs_per_page)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    
    context = {
        'page_obj': page_obj,
        'songs': page_obj,
    }
    
    return render(request, 'songs/partials/song_cards.html', context)


# ============================================================================
# URL PATTERNS TO ADD
# ============================================================================

"""
Add these to songs/urls.py:

from . import views_admin  # If you created a separate file

urlpatterns = [
    # ... existing patterns ...
    
    # Enhanced Admin Routes
    path('admin/users-v2/', views_admin.admin_users_dashboard_v2, name='admin_users_dashboard_v2'),
    path('admin/users/search/', views_admin.users_live_search, name='users_live_search'),
    path('admin/user/<int:user_id>/toggle-role/', views_admin.admin_toggle_user_role, name='admin_toggle_user_role'),
    path('admin/settings-v2/', views_admin.admin_settings_v2, name='admin_settings_v2'),
    path('admin/activity-log/', views_admin.admin_activity_log, name='admin_activity_log'),
    
    # HTMX Endpoints
    path('songs/htmx/search/', views_admin.songs_htmx_search, name='songs_htmx_search'),
]
"""
