# ============================================================================
# PERMISSION MIXINS AND DECORATORS
# Add to songs/permissions.py (create new file)
# ============================================================================

from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.decorators import login_required
from functools import wraps


# ============================================================================
# DECORATOR-BASED PERMISSIONS
# ============================================================================

def admin_required(view_func):
    """
    Decorator to require staff/superuser access.
    
    Usage:
        @login_required
        @admin_required
        def my_admin_view(request):
            ...
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "🔒 Please log in to access this page.")
            return redirect('login')
        
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "❌ Admin access required. You do not have permission.")
            return redirect('song_list')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


def superuser_required(view_func):
    """
    Decorator to require superuser access only.
    Used for critical operations like user deletion.
    
    Usage:
        @login_required
        @superuser_required
        def delete_user(request, user_id):
            ...
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "🔒 Please log in to access this page.")
            return redirect('login')
        
        if not request.user.is_superuser:
            messages.error(request, "❌ Superuser access required.")
            return redirect('song_list')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


def owner_or_admin_required(view_func):
    """
    Decorator to require object ownership or admin status.
    Expects 'pk' or 'id' in URL kwargs.
    
    Usage:
        @login_required
        @owner_or_admin_required
        def edit_song(request, pk):
            song = get_object_or_404(Song, pk=pk)
            ...
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "🔒 Please log in to access this page.")
            return redirect('login')
        
        # If admin, allow access
        if request.user.is_staff or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Check ownership (requires Song model import in actual usage)
        from .models import Song
        pk = kwargs.get('pk') or kwargs.get('id')
        if pk:
            try:
                obj = Song.objects.get(pk=pk)
                if obj.owner == request.user:
                    return view_func(request, *args, **kwargs)
            except Song.DoesNotExist:
                pass
        
        messages.error(request, "❌ You can only edit your own content.")
        return redirect('song_list')
    
    return _wrapped_view


# ============================================================================
# CLASS-BASED VIEW MIXINS
# ============================================================================

class AdminRequiredMixin(AccessMixin):
    """
    Mixin for class-based views requiring admin access.
    
    Usage:
        class AdminDashboardView(AdminRequiredMixin, ListView):
            model = User
            template_name = 'admin_dashboard.html'
    """
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "🔒 Please log in to access this page.")
            return redirect('login')
        
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "❌ Admin access required.")
            return redirect('song_list')
        
        return super().dispatch(request, *args, **kwargs)


class SuperuserRequiredMixin(AccessMixin):
    """
    Mixin for class-based views requiring superuser access.
    
    Usage:
        class CriticalSettingsView(SuperuserRequiredMixin, UpdateView):
            model = SiteConfig
            ...
    """
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "🔒 Please log in to access this page.")
            return redirect('login')
        
        if not request.user.is_superuser:
            messages.error(request, "❌ Superuser access required.")
            return redirect('song_list')
        
        return super().dispatch(request, *args, **kwargs)


class OwnerOrAdminRequiredMixin(AccessMixin):
    """
    Mixin for class-based views requiring ownership or admin access.
    
    Usage:
        class SongUpdateView(OwnerOrAdminRequiredMixin, UpdateView):
            model = Song
            owner_field = 'owner'  # Field name for ownership check
            ...
    """
    
    owner_field = 'owner'  # Override this in subclass if needed
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "🔒 Please log in to access this page.")
            return redirect('login')
        
        # Admin bypass
        if request.user.is_staff or request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        
        # Check ownership
        obj = self.get_object()
        owner = getattr(obj, self.owner_field, None)
        
        if owner != request.user:
            messages.error(request, "❌ You can only modify your own content.")
            return redirect('song_list')
        
        return super().dispatch(request, *args, **kwargs)


# ============================================================================
# EXAMPLE USAGE IN VIEWS
# ============================================================================

"""
# --- Function-Based View Examples ---

from .permissions import admin_required, owner_or_admin_required

@login_required
@admin_required
def admin_dashboard(request):
    users = User.objects.all()
    return render(request, 'admin_dashboard.html', {'users': users})


@login_required
@owner_or_admin_required
def song_edit(request, pk):
    song = get_object_or_404(Song, pk=pk)
    # Edit logic here
    return render(request, 'song_edit.html', {'song': song})


# --- Class-Based View Examples ---

from django.views.generic import ListView, UpdateView
from .permissions import AdminRequiredMixin, OwnerOrAdminRequiredMixin

class AdminUserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = 'admin_users.html'
    context_object_name = 'users'
    paginate_by = 20


class SongUpdateView(OwnerOrAdminRequiredMixin, UpdateView):
    model = Song
    fields = ['title_ta', 'lyrics_ta', 'cover_image']
    template_name = 'song_form.html'
    owner_field = 'owner'  # Check Song.owner field
    
    def get_success_url(self):
        return reverse('song_view', kwargs={'pk': self.object.pk})
"""


# ============================================================================
# CONTEXT PROCESSOR FOR PERMISSIONS
# Add to settings.py TEMPLATES['OPTIONS']['context_processors']
# ============================================================================

"""
# In songs/context_processors.py (create new file)

def user_permissions(request):
    '''
    Makes permission checks available in all templates.
    
    Usage in templates:
        {% if is_admin %}
            <a href="{% url 'admin_dashboard' %}">Admin Panel</a>
        {% endif %}
    '''
    if request.user.is_authenticated:
        return {
            'is_admin': request.user.is_staff or request.user.is_superuser,
            'is_superuser': request.user.is_superuser,
            'is_regular_user': not (request.user.is_staff or request.user.is_superuser),
        }
    
    return {
        'is_admin': False,
        'is_superuser': False,
        'is_regular_user': False,
    }


# Then add to settings.py:
TEMPLATES = [
    {
        ...
        'OPTIONS': {
            'context_processors': [
                ...
                'songs.context_processors.user_permissions',  # ← ADD THIS
            ],
        },
    },
]
"""
