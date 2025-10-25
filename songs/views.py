from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.db.models import Q, Count
from django.utils import timezone
from django.contrib.auth import get_user_model
from weasyprint import HTML, CSS
from .models import Song, AudioFile, SongAccess, AccessRequest, UserProfile
from .forms import SongForm, AddLanguageVersionForm, EnhancedUserRegistrationForm
import os, io, tempfile, shutil, zipfile, yt_dlp, requests, json

User = get_user_model()


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

# songs/views.py
from django.contrib.auth import login
from django.contrib import messages
from .forms import ContactAuthenticationForm  # 👈 import your form

from django.contrib.auth import authenticate, login, get_user_model

def user_login(request):
    """Enhanced login: allows login via username or contact number"""
    if request.method == "POST":
        username_or_phone = request.POST.get("username") or request.POST.get("contact")
        password = request.POST.get("password")

        print(f"🧩 DEBUG LOGIN: username_or_phone={username_or_phone}, password={'*' * len(password) if password else None}")

        if not username_or_phone or not password:
            messages.error(request, "Please enter both username/contact and password.")
            return render(request, "songs/login.html")

        user = None

        # Try username first
        try:
            user = User.objects.get(username=username_or_phone)
            print(f"✅ Found user by username: {user.username}")
        except User.DoesNotExist:
            # Try contact number lookup
            profiles = UserProfile.objects.filter(contact=username_or_phone)
            if profiles.count() == 1:
                user = profiles.first().user
                print(f"✅ Found user by contact: {user.username}")
            elif profiles.count() > 1:
                messages.error(
                    request,
                    "⚠️ Multiple accounts found with this phone number. Please contact admin."
                )
                print("⚠️ Multiple users share this contact number.")
                return render(request, "songs/login.html")
            else:
                print("❌ No user found by username or contact.")
                messages.error(request, "Invalid username, contact number, or password.")
                return render(request, "songs/login.html")

        # Authenticate and login
        if user:
            authenticated_user = authenticate(request, username=user.username, password=password)
            if authenticated_user:
                login(request, authenticated_user)
                messages.success(request, f"Welcome back, {authenticated_user.username} 🙏")
                return redirect(request.GET.get("next", "song_list"))
            else:
                print("❌ Authentication failed. Wrong password.")
                messages.error(request, "Incorrect password. Please try again.")
                return render(request, "songs/login.html")

    return render(request, "songs/login.html")
def user_logout(request):
    """User logout view"""
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("login")

from django.contrib import messages
from django.shortcuts import render, redirect
from songs.forms import EnhancedUserRegistrationForm

def user_register(request):
    """Enhanced user registration with validation"""
    if request.method == "POST":
        form = EnhancedUserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "🎉 Account created successfully! Please log in below.")
            return redirect("login")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = EnhancedUserRegistrationForm()
    return render(request, "songs/register.html", {"form": form})



def welcome(request):
    """Welcome/onboarding page"""
    if request.user.is_authenticated:
        return redirect("song_list")
    return render(request, "songs/welcome.html")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

# Real-time notifications removed - using AJAX polling instead


def user_can_access_song(user, song):
    """Check if user has permission to access song"""
    if not user.is_authenticated:
        return True
    if user.is_staff or user.is_superuser:
        return True
    if song.owner == user:
        return True
    return SongAccess.objects.filter(user=user, song=song).exists()


def get_accessible_songs_queryset(user):
    """Get queryset of songs accessible to user"""
    if not user.is_authenticated:
        return Song.objects.all()
    
    if user.is_staff or user.is_superuser:
        return Song.objects.all()
    
    owned_songs = Q(owner=user)
    accessible_songs = Q(id__in=SongAccess.objects.filter(user=user).values_list('song_id', flat=True))
    
    return Song.objects.filter(owned_songs | accessible_songs).distinct()


def get_or_create_audio_file(youtube_url=None, audio_file=None):
    """
    Get existing AudioFile or create new one.
    Returns tuple: (audio_file_obj, created, error_message)
    """
    
    # Check if YouTube URL already exists
    if youtube_url:
        # Normalize YouTube URL
        if "youtu.be/" in youtube_url:
            video_id = youtube_url.split("/")[-1].split("?")[0]
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Check if this URL already exists
        existing = AudioFile.objects.filter(youtube_url=youtube_url).first()
        if existing:
            return existing, False, None
        
        # Download from YouTube
        try:
            audio_obj, error = download_youtube_audio(youtube_url)
            if audio_obj:
                return audio_obj, True, None
            return None, False, error
        except Exception as e:
            return None, False, str(e)
    
    # Create from uploaded file
    elif audio_file:
        audio_obj = AudioFile.objects.create(
            source_type="file",
            title=audio_file.name,
            file_size=audio_file.size
        )
        audio_obj.audio_file.save(audio_file.name, audio_file)
        return audio_obj, True, None
    
    return None, False, "No audio source provided"


def download_youtube_audio(youtube_url):
    """
    Download audio from YouTube and create AudioFile instance.
    Returns tuple: (audio_file_obj, error_message)
    """
    temp_dir = None
    
    try:
        temp_dir = tempfile.mkdtemp(prefix="yt_")
        temp_path = os.path.join(temp_dir, "%(title)s.%(ext)s")
        
        ydl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "outtmpl": temp_path,
            "ffmpeg_location": "/usr/bin",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "extractor_args": {"youtube": {"player_client": ["android"]}},
            "http_headers": {
                "User-Agent": "com.google.android.youtube/18.21.35 (Linux; Android 13)",
                "Referer": "https://www.youtube.com/",
            },
            "retries": 5,
            "geo_bypass": True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            title = info.get("title", "YouTube Audio")
            duration = info.get("duration")
            
        # Find the downloaded MP3 file
        mp3_path = next(
            (os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.lower().endswith(".mp3")),
            None,
        )
        
        if not mp3_path:
            return None, "Converted MP3 file not found"
        
        # Create AudioFile instance
        audio_obj = AudioFile.objects.create(
            source_type="youtube",
            youtube_url=youtube_url,
            title=title,
            duration=duration,
            file_size=os.path.getsize(mp3_path)
        )
        
        # Save the audio file
        safe_title = title.replace("/", "_").replace("\\", "_").strip()
        with open(mp3_path, "rb") as f:
            audio_obj.audio_file.save(f"{safe_title}.mp3", ContentFile(f.read()))
        
        return audio_obj, None
        
    except Exception as e:
        return None, f"YouTube download failed: {str(e)}"
        
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def download_youtube_thumbnail(youtube_url):
    """Download thumbnail from YouTube video"""
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            thumbnail_url = info.get("thumbnail")
            
            if thumbnail_url:
                response = requests.get(thumbnail_url, timeout=10)
                if response.status_code == 200:
                    return ContentFile(response.content)
    except:
        pass
    return None


# ============================================================================
# SONG LIST & SEARCH
# ============================================================================

@login_required(login_url="login")
def song_list(request):
    """Display paginated list of songs with search, filter, and access control"""
    
    q = request.GET.get("q", "").strip()
    language = request.GET.get("language", "").strip()
    category = request.GET.get("category", "").strip()
    favorites_only = request.GET.get("favorites", "") == "1"
    owner_filter = request.GET.get("owner", "").strip()
    
    if request.user.is_staff:
        songs = Song.objects.all().select_related('owner', 'audio_file').prefetch_related('user_access')
    else:
        songs = get_accessible_songs_queryset(request.user).select_related('owner', 'audio_file').prefetch_related('user_access')
    
    if q:
        songs = songs.filter(
            Q(title_ta__icontains=q) |
            Q(title_te__icontains=q) |
            Q(title_en__icontains=q) |
            Q(lyrics_ta__icontains=q) |
            Q(lyrics_te__icontains=q) |
            Q(lyrics_en__icontains=q) |
            Q(owner__username__icontains=q)
        )
    
    if language:
        songs = songs.filter(language=language)
    
    if category:
        songs = songs.filter(category=category)
    
    if favorites_only:
        songs = songs.filter(is_favorite=True)
    
    if owner_filter:
        songs = songs.filter(owner__username__icontains=owner_filter)
    
    paginator = Paginator(songs.distinct(), 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    pending_requests_count = 0
    if request.user.is_staff:
        pending_requests_count = AccessRequest.objects.filter(status='pending').count()
    
    user_access_ids = set()
    user_pending_request_ids = set()
    if not request.user.is_staff:
        user_access_ids = set(SongAccess.objects.filter(user=request.user).values_list('song_id', flat=True))
        user_pending_request_ids = set(AccessRequest.objects.filter(
            user=request.user, 
            status='pending'
        ).values_list('song_id', flat=True))
    
    context = {
        "page_obj": page_obj,
        "q": q,
        "language": language,
        "category": category,
        "favorites_only": favorites_only,
        "owner_filter": owner_filter,
        "pending_requests_count": pending_requests_count,
        "user_access_ids": user_access_ids,
        "user_pending_request_ids": user_pending_request_ids,
    }
    
    # ✅ HTMX SUPPORT: Return partial HTML for live search
    if request.headers.get('HX-Request'):
        return render(request, "songs/partials/song_cards.html", context)
    
    return render(request, "songs/song_list_v3.html", context)


# ============================================================================
# SONG ADD
# ============================================================================

@login_required
def song_add(request):
    """Add new song with multilingual support and audio deduplication"""
    
    if request.method == "POST":
        form = SongForm(request.POST, request.FILES)
        
        if form.is_valid():
            song = form.save(commit=False)
            song.owner = request.user
            
            # Handle audio - YouTube URL or file upload
            youtube_url = form.cleaned_data.get('youtube_url')
            audio_upload = form.cleaned_data.get('audio_upload')
            
            if youtube_url or audio_upload:
                audio_obj, created, error = get_or_create_audio_file(
                    youtube_url=youtube_url,
                    audio_file=audio_upload
                )
                
                if audio_obj:
                    song.audio_file = audio_obj
                    
                    # Download thumbnail if from YouTube and no cover provided
                    if youtube_url and not song.cover_image and created:
                        thumbnail = download_youtube_thumbnail(youtube_url)
                        if thumbnail:
                            title = song.get_title() or "song"
                            song.cover_image.save(f"{title}.jpg", thumbnail)
                    
                    if not created:
                        messages.info(request, "Audio file already exists and was reused (deduplication).")
                elif error:
                    messages.error(request, f"Audio error: {error}")
                    return render(request, "songs/add.html", {"form": form})
            
            song.save()
            messages.success(request, f"Song '{song.get_title()}' added successfully!")
            return redirect("song_list")
    else:
        form = SongForm()
    
    return render(request, "songs/add.html", {"form": form})


# ============================================================================
# SONG EDIT
# ============================================================================

@login_required
def song_edit(request, pk):
    """Edit existing song"""
    
    song = get_object_or_404(Song, pk=pk)
    
    # Check ownership (optional - remove if all users can edit)
    if song.owner != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to edit this song.")
        return redirect("song_list")
    
    if request.method == "POST":
        form = SongForm(request.POST, request.FILES, instance=song)
        
        if form.is_valid():
            song = form.save(commit=False)
            
            # Handle new audio if provided
            youtube_url = form.cleaned_data.get('youtube_url')
            audio_upload = form.cleaned_data.get('audio_upload')
            
            if youtube_url or audio_upload:
                audio_obj, created, error = get_or_create_audio_file(
                    youtube_url=youtube_url,
                    audio_file=audio_upload
                )
                
                if audio_obj:
                    song.audio_file = audio_obj
                    if not created:
                        messages.info(request, "Existing audio file reused (deduplication).")
                elif error:
                    messages.error(request, f"Audio error: {error}")
                    return render(request, "songs/edit.html", {"form": form, "song": song})
            
            song.save()
            messages.success(request, "Song updated successfully!")
            return redirect("song_view", pk=song.pk)
    else:
        form = SongForm(instance=song)
    
    return render(request, "songs/edit.html", {"form": form, "song": song})


# ============================================================================
# ADD LANGUAGE VERSION
# ============================================================================
from django.http import JsonResponse
from songs.models import UserProfile

def check_contact(request):
    """AJAX: Check if contact number already exists"""
    contact = request.GET.get("contact", "").strip()
    exists = UserProfile.objects.filter(contact=contact).exists()
    return JsonResponse({"exists": exists})


@login_required
def song_add_language(request, pk):
    """Add a new language version to existing song"""
    
    song = get_object_or_404(Song, pk=pk)
    
    # Check if all languages are already present
    if len(song.available_languages()) >= 3:
        messages.info(request, "All language versions already exist for this song.")
        return redirect("song_view", pk=song.pk)
    
    if request.method == "POST":
        form = AddLanguageVersionForm(request.POST, song=song)
        
        if form.is_valid():
            language = form.cleaned_data['language']
            title = form.cleaned_data['title']
            lyrics = form.cleaned_data['lyrics']
            
            # Update the appropriate fields based on language
            if language == "tamil":
                song.title_ta = title
                song.lyrics_ta = lyrics
            elif language == "telugu":
                song.title_te = title
                song.lyrics_te = lyrics
            elif language == "english":
                song.title_en = title
                song.lyrics_en = lyrics
            
            song.save()
            messages.success(request, f"{dict(form.fields['language'].choices)[language]} version added successfully!")
            return redirect("song_view", pk=song.pk)
    else:
        form = AddLanguageVersionForm(song=song)
    
    return render(request, "songs/add_language.html", {"form": form, "song": song})


# ============================================================================
# SONG VIEW/DETAIL
# ============================================================================

def song_view(request, pk):
    """View song details with multilingual display and access control"""
    
    song = get_object_or_404(Song, pk=pk)
    
    if not user_can_access_song(request.user, song):
        messages.warning(request, "🚫 You don't have access to this song. Request access from admin.")
        return redirect("song_list")
    
    song.play_count += 1
    song.save(update_fields=['play_count'])
    
    available_langs = song.available_languages()
    missing_langs = song.missing_languages()
    
    has_access_request = False
    if request.user.is_authenticated:
        has_access_request = AccessRequest.objects.filter(
            user=request.user,
            song=song,
            status='pending'
        ).exists()
    
    context = {
        "song": song,
        "available_langs": available_langs,
        "missing_langs": missing_langs,
        "has_access_request": has_access_request,
    }
    
    return render(request, "songs/view.html", context)


# ============================================================================
# SONG DELETE
# ============================================================================

@login_required
def song_delete(request, pk):
    """Delete song - handles both GET (confirmation page) and POST (actual delete)"""
    
    song = get_object_or_404(Song, pk=pk)
    
    # Check ownership (optional - remove if all users can delete)
    if song.owner != request.user and not request.user.is_staff:
        if request.method == "POST":
            return JsonResponse({"error": "Permission denied"}, status=403)
        messages.error(request, "You don't have permission to delete this song.")
        return redirect("song_list")
    
    if request.method == "POST":
        title = song.get_title()
        song.delete()
        
        # Return JSON response for AJAX requests
        if request.headers.get('Content-Type') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"success": True, "message": f"Song '{title}' was deleted successfully."})
        
        messages.success(request, f"Song '{title}' was deleted successfully.")
        return redirect("song_list")
    
    # GET request - show confirmation page (optional, for non-AJAX deletes)
    return render(request, "songs/confirm_delete.html", {"song": song})


# ============================================================================
# TOGGLE FAVORITE
# ============================================================================

@login_required
def song_toggle_favorite(request, pk):
    """Toggle favorite status for a song (AJAX endpoint)"""
    
    if request.method == "POST":
        song = get_object_or_404(Song, pk=pk)
        song.is_favorite = not song.is_favorite
        song.save(update_fields=['is_favorite'])
        
        return JsonResponse({
            "success": True,
            "is_favorite": song.is_favorite
        })
    
    return JsonResponse({"success": False}, status=400)


# ============================================================================
# DOWNLOAD AUDIO FILE
# ============================================================================

def song_download(request, pk):
    """Download audio file or redirect to YouTube"""
    
    song = get_object_or_404(Song, pk=pk)
    
    # Check if audio file exists
    if song.audio_file and song.audio_file.audio_file:
        # Direct download of MP3 file
        response = HttpResponse(song.audio_file.audio_file.read(), content_type="audio/mpeg")
        filename = f"{song.get_title()}.mp3"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    
    # Check for legacy audio field
    elif song.audio:
        response = HttpResponse(song.audio.read(), content_type="audio/mpeg")
        filename = f"{song.get_title()}.mp3"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    
    # If only YouTube URL exists, redirect to it
    elif song.audio_file and song.audio_file.youtube_url:
        return redirect(song.audio_file.youtube_url)
    
    # No audio available
    else:
        messages.warning(request, "🎧 Audio not available for this song.")
        return redirect("song_view", pk=pk)


# ============================================================================
# DOWNLOAD SONG AS PDF
# ============================================================================

def song_download_pdf(request, pk):
    """Download song as PDF with all language versions"""
    
    song = get_object_or_404(Song, pk=pk)
    
    html_string = render_to_string("songs/pdf_template.html", {"song": song})
    html = HTML(string=html_string, base_url=request.build_absolute_uri("/"))
    
    css = CSS(string="""
        @page {
            size: A4;
            margin: 1.5cm;
            background: linear-gradient(180deg, #fffdf8, #fffaf2);
            @bottom-center {
                content: "Swamiye Saranam Ayyappa • Page " counter(page);
                font-family: 'Arial', sans-serif;
                font-size: 9pt;
                color: #7c2d12;
            }
        }
        body {
            font-family: 'Arial', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
        }
        h1 {
            color: #92400e;
            text-align: center;
            font-size: 20pt;
        }
        .language-section {
            margin-bottom: 2cm;
            padding: 0.5cm;
            border: 1px solid #fbbf24;
            border-radius: 8px;
        }
        .lyrics {
            white-space: pre-wrap;
            font-size: 12pt;
            line-height: 1.8;
        }
    """)
    
    pdf = html.write_pdf(stylesheets=[css])
    
    response = HttpResponse(pdf, content_type="application/pdf")
    filename = f"{song.get_title()}_multilingual.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    
    return response


# ============================================================================
# BULK DOWNLOAD AS ZIP
# ============================================================================

def bulk_download(request):
    """Download multiple songs as ZIP file with audio and lyrics"""
    
    ids = request.GET.get("ids", "")
    
    if not ids:
        messages.error(request, "No songs selected for download.")
        return redirect("song_list")
    
    # Parse IDs
    try:
        id_list = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    except ValueError:
        messages.error(request, "Invalid song IDs provided.")
        return redirect("song_list")
    
    if not id_list:
        messages.error(request, "No valid songs selected.")
        return redirect("song_list")
    
    # Get songs
    songs = Song.objects.filter(id__in=id_list).select_related('audio_file')
    
    if not songs.exists():
        messages.error(request, "No songs found with the provided IDs.")
        return redirect("song_list")
    
    # Create ZIP file in memory
    mem = io.BytesIO()
    files_added = 0
    
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        for song in songs:
            song_title = song.get_title().replace("/", "_").replace("\\", "_")
            
            # Add audio file if available
            audio_added = False
            if song.audio_file and song.audio_file.audio_file:
                try:
                    song.audio_file.audio_file.seek(0)
                    audio_data = song.audio_file.audio_file.read()
                    filename = f"{song_title}.mp3"
                    zf.writestr(filename, audio_data)
                    audio_added = True
                    files_added += 1
                except Exception as e:
                    pass
            elif song.audio:
                try:
                    song.audio.seek(0)
                    audio_data = song.audio.read()
                    filename = f"{song_title}.mp3"
                    zf.writestr(filename, audio_data)
                    audio_added = True
                    files_added += 1
                except Exception as e:
                    pass
            
            # Add lyrics as text file
            lyrics_content = ""
            for lang_code, lang_name in song.available_languages():
                if lang_code == "tamil":
                    lyrics = song.lyrics_ta
                    title = song.title_ta
                elif lang_code == "telugu":
                    lyrics = song.lyrics_te
                    title = song.title_te
                elif lang_code == "english":
                    lyrics = song.lyrics_en
                    title = song.title_en
                else:
                    continue
                    
                if lyrics:
                    lyrics_content += f"=== {lang_name} ===\n"
                    lyrics_content += f"{title}\n\n"
                    lyrics_content += f"{lyrics}\n\n\n"
            
            if lyrics_content:
                zf.writestr(f"{song_title}_lyrics.txt", lyrics_content)
                files_added += 1
    
    if files_added == 0:
        messages.warning(request, "No audio or lyrics files were available for the selected songs.")
        return redirect("song_list")
    
    mem.seek(0)
    
    response = HttpResponse(mem.read(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="bhajan_songs_bundle.zip"'
    
    return response


# ============================================================================
# ACCESS CONTROL
# ============================================================================

@login_required
def request_song_access(request, pk):
    """Request access to a song"""
    song = get_object_or_404(Song, pk=pk)
    
    if user_can_access_song(request.user, song):
        messages.info(request, "You already have access to this song.")
        return redirect("song_view", pk=pk)
    
    existing_request = AccessRequest.objects.filter(
        user=request.user,
        song=song,
        status='pending'
    ).first()
    
    if existing_request:
        messages.info(request, "🔔 Access request already pending. Admin will review soon.")
        return redirect("song_list")
    
    if request.method == "POST":
        message = request.POST.get('message', '').strip()
        access_request = AccessRequest.objects.create(
            user=request.user,
            song=song,
            message=message
        )
        
        messages.success(request, "✅ Access request sent to admin!")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Access request sent to admin!'
            })
        
        return redirect("song_list")
    
    return render(request, "songs/request_access.html", {"song": song})


@login_required
def admin_access_requests(request):
    """Admin view to manage access requests"""
    if not request.user.is_staff:
        messages.error(request, "Admin access only.")
        return redirect("song_list")
    
    pending_requests = AccessRequest.objects.filter(status='pending').select_related('user', 'song')
    reviewed_requests = AccessRequest.objects.filter(status__in=['approved', 'denied']).select_related('user', 'song', 'reviewed_by')[:50]
    
    context = {
        'pending_requests': pending_requests,
        'reviewed_requests': reviewed_requests,
    }
    
    return render(request, "songs/admin_access_requests.html", context)


@login_required
def admin_grant_access(request, pk):
    """Grant access request"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    access_request = get_object_or_404(AccessRequest, pk=pk)
    
    SongAccess.objects.get_or_create(
        user=access_request.user,
        song=access_request.song,
        defaults={'granted_by': request.user}
    )
    
    access_request.status = 'approved'
    access_request.reviewed_by = request.user
    access_request.reviewed_at = timezone.now()
    access_request.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"success": True, "message": f"Access granted to {access_request.user.username}"})
    
    messages.success(request, f"✅ Access granted to {access_request.user.username}")
    return redirect("admin_access_requests")


@login_required
def admin_deny_access(request, pk):
    """Deny access request"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    access_request = get_object_or_404(AccessRequest, pk=pk)
    
    access_request.status = 'denied'
    access_request.reviewed_by = request.user
    access_request.reviewed_at = timezone.now()
    access_request.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"success": True, "message": f"Access denied for {access_request.user.username}"})
    
    messages.info(request, f"Access denied for {access_request.user.username}")
    return redirect("admin_access_requests")


@login_required
def admin_manage_access(request):
    """Bulk grant/revoke access"""
    if not request.user.is_staff:
        messages.error(request, "Admin access only.")
        return redirect("song_list")
    
    if request.method == "POST":
        action = request.POST.get('action')
        user_ids = request.POST.getlist('users')
        song_ids = request.POST.getlist('songs')
        
        if action == 'grant':
            count = 0
            for user_id in user_ids:
                for song_id in song_ids:
                    _, created = SongAccess.objects.get_or_create(
                        user_id=user_id,
                        song_id=song_id,
                        defaults={'granted_by': request.user}
                    )
                    if created:
                        count += 1
            messages.success(request, f"✅ Granted {count} access permissions")
        
        elif action == 'revoke':
            count = SongAccess.objects.filter(user_id__in=user_ids, song_id__in=song_ids).delete()[0]
            messages.success(request, f"🗑️ Revoked {count} access permissions")
        
        return redirect("admin_manage_access")
    
    users = User.objects.all().order_by('username')
    songs = Song.objects.all().order_by('-uploaded_at')
    accesses = SongAccess.objects.select_related('user', 'song', 'granted_by').order_by('-granted_at')[:100]
    
    context = {
        'users': users,
        'songs': songs,
        'accesses': accesses,
    }
    
    return render(request, "songs/admin_manage_access.html", context)


@login_required
def admin_users_dashboard(request):
    """Custom admin dashboard for user management with PDF export and HTMX live search"""
    if not request.user.is_staff:
        messages.error(request, "Admin access only.")
        return redirect("song_list")
    
    search = request.GET.get('search', '').strip()
    filter_region = request.GET.get('region', '').strip()
    filter_language = request.GET.get('language', '').strip()
    filter_role = request.GET.get('role', '').strip()
    export_pdf = request.GET.get('export', '').lower() == 'pdf'
    single_user_id = request.GET.get('user', '')
    
    # ✅ OPTIMIZED QUERY: select_related to avoid N+1
    users = User.objects.annotate(
        access_count=Count('song_access'),
        song_count=Count('songs')
    ).select_related('profile').order_by('-date_joined')
    
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(profile__region__icontains=search) |
            Q(profile__city__icontains=search)
        )
    
    if filter_region:
        users = users.filter(profile__region__icontains=filter_region)
    
    if filter_language:
        users = users.filter(profile__language_preference=filter_language)
    
    if filter_role == 'staff':
        users = users.filter(is_staff=True)
    elif filter_role == 'user':
        users = users.filter(is_staff=False)
    
    if single_user_id:
        users = users.filter(id=single_user_id)
    
    # PDF Export
    if export_pdf:
        return generate_users_pdf(request, users, single_user=bool(single_user_id))
    
    regions = UserProfile.objects.values_list('region', flat=True).distinct().order_by('region')
    
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'filter_region': filter_region,
        'filter_language': filter_language,
        'filter_role': filter_role,
        'regions': [r for r in regions if r],
        'total_users': User.objects.count(),
        'total_staff': User.objects.filter(is_staff=True).count(),
        'total_active': User.objects.filter(is_active=True).count(),
    }
    
    # ✅ HTMX SUPPORT: Return partial HTML for AJAX requests
    if request.headers.get('HX-Request'):
        # Return only the table body rows for live search
        return render(request, "songs/partials/user_table_rows.html", context)
    
    return render(request, "songs/admin_users_dashboard_v2.html", context)


def generate_users_pdf(request, users_queryset, single_user=False):
    """Generate PDF report for users"""
    users_list = list(users_queryset)
    
    html_string = render_to_string('songs/admin_users_pdf.html', {
        'users': users_list,
        'single_user': single_user,
        'generated_by': request.user.username,
        'generated_at': timezone.now(),
        'total_count': len(users_list),
    })
    
    html = HTML(string=html_string, base_url=request.build_absolute_uri("/"))
    pdf_file = html.write_pdf()
    
    if single_user and users_list:
        filename = f"user_{users_list[0].username}_report.pdf"
    else:
        filename = f"users_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
def admin_user_detail(request, user_id):
    """Get user details for modal (AJAX)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    user = get_object_or_404(User, id=user_id)
    
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = None
    
    accesses = SongAccess.objects.filter(user=user).select_related('song', 'granted_by')
    requests = AccessRequest.objects.filter(user=user).select_related('song')[:10]
    
    data = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'date_joined': user.date_joined.strftime('%B %d, %Y'),
        'is_staff': user.is_staff,
        'is_active': user.is_active,
        'profile': {
            'language': profile.get_language_preference_display() if profile else 'N/A',
            'region': profile.region if profile else 'N/A',
            'city': profile.city if profile else 'N/A',
            'contact': profile.contact if profile else 'N/A',
        } if profile else None,
        'access_count': accesses.count(),
        'accesses': [
            {
                'song': access.song.display_title,
                'granted_at': access.granted_at.strftime('%b %d, %Y'),
                'granted_by': access.granted_by.username if access.granted_by else 'System'
            }
            for access in accesses[:10]
        ],
        'recent_requests': [
            {
                'song': req.song.display_title,
                'status': req.get_status_display(),
                'requested_at': req.requested_at.strftime('%b %d, %Y')
            }
            for req in requests
        ]
    }
    
    return JsonResponse(data)


@login_required
def admin_user_song_access(request, user_id):
    """Manage song access for a specific user"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'GET':
        songs = Song.objects.all().order_by('title_ta', 'title_te', 'title_en')
        user_accesses = set(SongAccess.objects.filter(user=user).values_list('song_id', flat=True))
        
        data = {
            'user': {
                'id': user.id,
                'username': user.username
            },
            'songs': [
                {
                    'id': song.id,
                    'title': song.display_title,
                    'has_access': song.id in user_accesses
                }
                for song in songs
            ]
        }
        
        return JsonResponse(data)
    
    elif request.method == 'POST':
        data = json.loads(request.body)
        song_ids = data.get('song_ids', [])
        
        SongAccess.objects.filter(user=user).delete()
        
        for song_id in song_ids:
            SongAccess.objects.create(
                user=user,
                song_id=song_id,
                granted_by=request.user
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Updated access for {user.username}',
            'count': len(song_ids)
        })
    
    return JsonResponse({'error': 'Invalid method'}, status=400)


@login_required
def admin_revoke_all_access(request, user_id):
    """Revoke all access for a user"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        count = SongAccess.objects.filter(user=user).delete()[0]
        
        return JsonResponse({
            'success': True,
            'message': f'Revoked all access for {user.username}',
            'count': count
        })
    
    return JsonResponse({'error': 'Invalid method'}, status=400)


# ============================================================================
# PUSH NOTIFICATIONS
# ============================================================================

@login_required
def admin_send_notification(request):
    """Admin interface to send push notifications"""
    if not request.user.is_staff:
        messages.error(request, "Admin access only.")
        return redirect("song_list")
    
    if request.method == "POST":
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        url = request.POST.get('url', '/songs/')
        
        if title and body:
            try:
                send_push_notification(title, body, url)
                messages.success(request, "🔔 Notification sent to all users!")
            except Exception as e:
                messages.error(request, f"Failed to send notification: {str(e)}")
        else:
            messages.error(request, "Title and message are required.")
        
        return redirect("admin_send_notification")
    
    return render(request, "songs/admin_send_notification.html")


def send_push_notification(title, body, url='/'):
    """Send push notification via Firebase (requires setup)"""
    try:
        import firebase_admin
        from firebase_admin import messaging
        
        message = messaging.Message(
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    title=title,
                    body=body,
                    icon='/static/icons/icon-192.png',
                ),
                fcm_options=messaging.WebpushFCMOptions(link=url)
            ),
            topic="all_users"
        )
        
        response = messaging.send(message)
        print(f"Successfully sent notification: {response}")
        return True
    except ImportError:
        print("Firebase Admin SDK not installed or configured")
        return False
    except Exception as e:
        print(f"Notification error: {str(e)}")
        raise


# ============================================================================
# OFFLINE PAGE
# ============================================================================

def offline_page(request):
    """Offline fallback page for PWA"""
    return render(request, "songs/offline.html")


# ============================================================================
# USER ACCESS REQUEST VIEWS
# ============================================================================

@login_required
def my_requests(request):
    """View for users to see their own access requests"""
    filter_status = request.GET.get('status', 'all')
    
    requests_qs = AccessRequest.objects.filter(user=request.user).select_related('song', 'song__owner', 'reviewed_by').order_by('-requested_at')
    
    if filter_status != 'all':
        requests_qs = requests_qs.filter(status=filter_status)
    
    stats = {
        'total': AccessRequest.objects.filter(user=request.user).count(),
        'pending': AccessRequest.objects.filter(user=request.user, status='pending').count(),
        'approved': AccessRequest.objects.filter(user=request.user, status='approved').count(),
        'denied': AccessRequest.objects.filter(user=request.user, status='denied').count(),
    }
    
    paginator = Paginator(requests_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'requests': page_obj,
        'page_obj': page_obj,
        'stats': stats,
        'filter_status': filter_status,
    }
    
    return render(request, "songs/my_requests.html", context)


# ============================================================================
# ASTOTHARAM VIEWS
# ============================================================================

@login_required
def astotharam_list(request):
    """List all astotharams with filters"""
    from .models import Astotharam, CATEGORY_CHOICES
    
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    language = request.GET.get('language', '').strip()
    
    items = Astotharam.objects.all().select_related('owner')
    
    if q:
        items = items.filter(
            Q(title_ta__icontains=q) |
            Q(title_te__icontains=q) |
            Q(title_en__icontains=q) |
            Q(content_ta__icontains=q) |
            Q(content_te__icontains=q) |
            Q(content_en__icontains=q)
        )
    
    if category:
        items = items.filter(category=category)
    
    if language:
        items = items.filter(language=language)
    
    paginator = Paginator(items, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'q': q,
        'category': category,
        'language': language,
        'categories': CATEGORY_CHOICES,
    }
    
    return render(request, 'songs/astotharam_list.html', context)


@login_required
def astotharam_add(request):
    """Add new astotharam (admin only)"""
    if not request.user.is_staff:
        messages.error(request, "Admin access only.")
        return redirect('astotharam_list')
    
    from .models import Astotharam, CATEGORY_CHOICES, LANGUAGE_CHOICES
    
    if request.method == 'POST':
        astotharam = Astotharam.objects.create(
            owner=request.user,
            title_ta=request.POST.get('title_ta', ''),
            title_te=request.POST.get('title_te', ''),
            title_en=request.POST.get('title_en', ''),
            content_ta=request.POST.get('content_ta', ''),
            content_te=request.POST.get('content_te', ''),
            content_en=request.POST.get('content_en', ''),
            language=request.POST.get('language', 'tamil'),
            category=request.POST.get('category', 'others'),
        )
        messages.success(request, '✅ Astotharam added successfully!')
        return redirect('astotharam_view', pk=astotharam.pk)
    
    return render(request, 'songs/astotharam_form.html', {
        'categories': CATEGORY_CHOICES,
        'languages': LANGUAGE_CHOICES,
        'action': 'Add',
    })


@login_required
def astotharam_view(request, pk):
    """View astotharam details"""
    from .models import Astotharam
    astotharam = get_object_or_404(Astotharam, pk=pk)
    return render(request, 'songs/astotharam_view.html', {'astotharam': astotharam})


@login_required
def astotharam_edit(request, pk):
    """Edit astotharam (admin only)"""
    if not request.user.is_staff:
        messages.error(request, "Admin access only.")
        return redirect('astotharam_list')
    
    from .models import Astotharam, CATEGORY_CHOICES, LANGUAGE_CHOICES
    astotharam = get_object_or_404(Astotharam, pk=pk)
    
    if request.method == 'POST':
        astotharam.title_ta = request.POST.get('title_ta', '')
        astotharam.title_te = request.POST.get('title_te', '')
        astotharam.title_en = request.POST.get('title_en', '')
        astotharam.content_ta = request.POST.get('content_ta', '')
        astotharam.content_te = request.POST.get('content_te', '')
        astotharam.content_en = request.POST.get('content_en', '')
        astotharam.language = request.POST.get('language', 'tamil')
        astotharam.category = request.POST.get('category', 'others')
        astotharam.save()
        messages.success(request, '✅ Astotharam updated successfully!')
        return redirect('astotharam_view', pk=astotharam.pk)
    
    return render(request, 'songs/astotharam_form.html', {
        'astotharam': astotharam,
        'categories': CATEGORY_CHOICES,
        'languages': LANGUAGE_CHOICES,
        'action': 'Edit',
    })


@login_required
def astotharam_delete(request, pk):
    """Delete astotharam (admin only)"""
    if not request.user.is_staff:
        messages.error(request, "Admin access only.")
        return redirect('astotharam_list')

    from .models import Astotharam
    astotharam = get_object_or_404(Astotharam, pk=pk)

    if request.method == 'POST':
        astotharam.delete()
        messages.success(request, '✅ Astotharam deleted successfully!')
        return redirect('astotharam_list')

    return render(request, 'songs/astotharam_confirm_delete.html', {
        'astotharam': astotharam,   # ✅ renamed from 'item'
        'item_type': 'Astotharam',
        'cancel_url': 'astotharam_list',
    })


# ============================================================================
# SARANAGHOSHA VIEWS
# ============================================================================

@login_required
def saranaghosha_list(request):
    """List all saranagoshas with filters"""
    from .models import Saranaghosha, CATEGORY_CHOICES
    
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    language = request.GET.get('language', '').strip()
    
    items = Saranaghosha.objects.all().select_related('owner')
    
    if q:
        items = items.filter(
            Q(title_ta__icontains=q) |
            Q(title_te__icontains=q) |
            Q(title_en__icontains=q) |
            Q(content_ta__icontains=q) |
            Q(content_te__icontains=q) |
            Q(content_en__icontains=q)
        )
    
    if category:
        items = items.filter(category=category)
    
    if language:
        items = items.filter(language=language)
    
    paginator = Paginator(items, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'q': q,
        'category': category,
        'language': language,
        'categories': CATEGORY_CHOICES,
    }
    
    return render(request, 'songs/saranaghosha_list.html', context)


@login_required
def saranaghosha_add(request):
    """Add new saranaghosha (admin only)"""
    if not request.user.is_staff:
        messages.error(request, "Admin access only.")
        return redirect('saranaghosha_list')
    
    from .models import Saranaghosha, CATEGORY_CHOICES, LANGUAGE_CHOICES
    
    if request.method == 'POST':
        saranaghosha = Saranaghosha.objects.create(
            owner=request.user,
            title_ta=request.POST.get('title_ta', ''),
            title_te=request.POST.get('title_te', ''),
            title_en=request.POST.get('title_en', ''),
            content_ta=request.POST.get('content_ta', ''),
            content_te=request.POST.get('content_te', ''),
            content_en=request.POST.get('content_en', ''),
            language=request.POST.get('language', 'tamil'),
            category=request.POST.get('category', 'others'),
        )
        messages.success(request, '✅ Saranaghosha added successfully!')
        return redirect('saranaghosha_view', pk=saranaghosha.pk)
    
    return render(request, 'songs/saranaghosha_form.html', {
        'categories': CATEGORY_CHOICES,
        'languages': LANGUAGE_CHOICES,
        'action': 'Add',
    })


@login_required
def saranaghosha_view(request, pk):
    """View saranaghosha details"""
    from .models import Saranaghosha
    saranaghosha = get_object_or_404(Saranaghosha, pk=pk)
    return render(request, 'songs/saranaghosha_view.html', {'saranaghosha': saranaghosha})


@login_required
def saranaghosha_edit(request, pk):
    """Edit saranaghosha (admin only)"""
    if not request.user.is_staff:
        messages.error(request, "Admin access only.")
        return redirect('saranaghosha_list')
    
    from .models import Saranaghosha, CATEGORY_CHOICES, LANGUAGE_CHOICES
    saranaghosha = get_object_or_404(Saranaghosha, pk=pk)
    
    if request.method == 'POST':
        saranaghosha.title_ta = request.POST.get('title_ta', '')
        saranaghosha.title_te = request.POST.get('title_te', '')
        saranaghosha.title_en = request.POST.get('title_en', '')
        saranaghosha.content_ta = request.POST.get('content_ta', '')
        saranaghosha.content_te = request.POST.get('content_te', '')
        saranaghosha.content_en = request.POST.get('content_en', '')
        saranaghosha.language = request.POST.get('language', 'tamil')
        saranaghosha.category = request.POST.get('category', 'others')
        saranaghosha.save()
        messages.success(request, '✅ Saranaghosha updated successfully!')
        return redirect('saranaghosha_view', pk=saranaghosha.pk)
    
    return render(request, 'songs/saranaghosha_form.html', {
        'saranaghosha': saranaghosha,
        'categories': CATEGORY_CHOICES,
        'languages': LANGUAGE_CHOICES,
        'action': 'Edit',
    })


@login_required
def saranaghosha_delete(request, pk):
    """Delete saranaghosha (admin only)"""
    if not request.user.is_staff:
        messages.error(request, "Admin access only.")
        return redirect('saranaghosha_list')
    
    from .models import Saranaghosha
    saranaghosha = get_object_or_404(Saranaghosha, pk=pk)
    
    if request.method == 'POST':
        saranaghosha.delete()
        messages.success(request, '✅ Saranaghosha deleted successfully!')
        return redirect('saranaghosha_list')
    
    return render(request, 'songs/confirm_delete.html', {
        'item': saranaghosha,
        'item_type': 'Saranaghosha',
        'cancel_url': 'saranaghosha_list',
    })


# ============================================================================
# ADMIN SETTINGS VIEW
# ============================================================================

@login_required
def admin_settings(request):
    """Admin settings panel"""
    if not request.user.is_staff:
        messages.error(request, "Admin access only.")
        return redirect('song_list')
    
    from .models import AppSettings, CATEGORY_CHOICES
    settings_obj = AppSettings.get_settings()
    
    if request.method == 'POST':
        settings_obj.site_title = request.POST.get('site_title', settings_obj.site_title)
        settings_obj.site_subtitle = request.POST.get('site_subtitle', settings_obj.site_subtitle)
        settings_obj.primary_color = request.POST.get('primary_color', settings_obj.primary_color)
        settings_obj.secondary_color = request.POST.get('secondary_color', settings_obj.secondary_color)
        settings_obj.enable_categories = request.POST.get('enable_categories') == 'on'
        settings_obj.enable_astotharam = request.POST.get('enable_astotharam') == 'on'
        settings_obj.enable_saranaghosha = request.POST.get('enable_saranaghosha') == 'on'
        settings_obj.updated_by = request.user
        settings_obj.save()
        
        messages.success(request, '✅ Settings updated successfully!')
        return redirect('admin_settings')
    
    context = {
        'settings': settings_obj,
        'categories': CATEGORY_CHOICES,
    }
    
    return render(request, 'songs/admin_settings.html', context)
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.hashers import make_password
from songs.models import PasswordResetOTP
from datetime import datetime, timedelta
import random, string

# Optional: import Twilio
from twilio.rest import Client

User = get_user_model()

# ------------------------------
# Twilio Config (direct — no .env needed)
# ------------------------------
import os

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")





def send_otp(phone, otp):
    """Try Twilio Messaging → Verify → Console fallback"""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    # Devotional custom message
    message_body = (
        f"🕉️ Swamiye Saranam Ayyappa 🙏\n\n"
        f"Your OTP for password reset is: {otp}\n"
        f"This code is valid for 10 minutes.\n"
        f"Do not share this code with anyone."
    )

    try:
        # First try direct messaging (lets you fully control content)
        sms = client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=phone
        )
        print(f"✅ OTP sent via Twilio SMS to {phone} (SID: {sms.sid})")

    except Exception as e1:
        print("⚠️ SMS send failed, trying Verify API:", e1)
        try:
            verification = client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID).verifications.create(
                to=phone, channel="sms"
            )
            print(f"✅ OTP sent via Twilio Verify to {phone} (SID: {verification.sid})")
        except Exception as e2:
            print("⚠️ Twilio Verify failed, fallback to console:", e2)
            print(f"📞 [Console OTP] {otp} → {phone}")
# ------------------------------
# STEP 1: REQUEST PASSWORD RESET (by phone)
# ------------------------------
from django.contrib.auth.models import User
from django.http import HttpResponse


def create_admin(request):
    """
    ⚠️ Temporary utility view to create a Django superuser via URL parameters.
    Example:
      /create-admin/?username=admin&password=Venkat@123
    """
    username = request.GET.get("username")
    password = request.GET.get("password")

    # Basic validation
    if not username or not password:
        return HttpResponse("❌ Missing parameters. Use ?username=<name>&password=<pass>")

    # Check if user already exists
    if User.objects.filter(username=username).exists():
        return HttpResponse(f"⚠️ User '{username}' already exists!")

    try:
        User.objects.create_superuser(username=username, email="", password=password)
        return HttpResponse(f"✅ Superuser '{username}' created successfully! You can now log in at /admin/")
    except Exception as e:
        return HttpResponse(f"❌ Error creating admin: {e}")
def reset_with_phone(request):
    if request.method == "POST":
        phone = request.POST.get("phone")
        print("📞 Entered phone:", phone)

        if not phone:
            messages.error(request, "Please enter your phone number.")
            return redirect("reset_with_phone")

        if not phone.startswith("+91"):
            phone = "+91" + phone.strip()

        try:
            user = User.objects.get(profile__contact=phone)

            # ✅ Do not create your own OTP — just trigger Twilio Verify
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            verification = client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID).verifications.create(
                to=phone,
                channel="sms"
            )
            print(f"✅ OTP sent via Twilio Verify to {phone} (SID: {verification.sid})")

            # Store session for later verification
            request.session["reset_user_id"] = user.id
            request.session["reset_phone"] = phone
            messages.success(request, f"OTP sent to {phone}.")
            return redirect("verify_otp")

        except User.DoesNotExist:
            messages.error(request, "No user found with this phone number.")
        except Exception as e:
            print("❌ Error:", e)
            messages.error(request, "Something went wrong. Please try again.")

    return render(request, "songs/reset_with_phone.html")

# ------------------------------
# STEP 2: VERIFY OTP
# ------------------------------
def verify_otp(request):
    if request.method == "POST":
        otp = request.POST.get("otp")
        phone = request.session.get("reset_phone")
        user_id = request.session.get("reset_user_id")

        if not phone or not user_id:
            messages.error(request, "Session expired. Please try again.")
            return redirect("reset_with_phone")

        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            verification_check = client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID).verification_checks.create(
                to=phone,
                code=otp
            )

            if verification_check.status == "approved":
                request.session["otp_verified"] = True
                messages.success(request, "✅ OTP verified successfully.")
                return redirect("set_new_password")
            else:
                messages.error(request, "❌ Invalid or expired OTP. Please try again.")

        except Exception as e:
            print("❌ OTP verify error:", e)
            messages.error(request, "Something went wrong while verifying OTP.")

    return render(request, "songs/verify_otp.html")

# ------------------------------
# STEP 3: SET NEW PASSWORD
# ------------------------------
def set_new_password(request):
    user_id = request.session.get("reset_user_id")
    otp_verified = request.session.get("otp_verified")

    if not user_id or not otp_verified:
        messages.error(request, "Unauthorized access. Please verify OTP first.")
        return redirect("reset_with_phone")

    if request.method == "POST":
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect("set_new_password")

        try:
            user = User.objects.get(id=user_id)
            user.password = make_password(password1)
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, "✅ Password reset successful. You can now log in.")
            request.session.flush()
            return redirect("login")
        except Exception as e:
            print("❌ Password reset error:", e)
            messages.error(request, "Unable to reset password. Try again.")

    return render(request, "songs/set_new_password.html")


# ------------------------------
# STEP 4: RESEND OTP (if needed)
# ------------------------------
def resend_otp(request):
    phone = request.session.get("reset_phone")
    if not phone:
        messages.error(request, "Session expired. Please start again.")
        return redirect("reset_with_phone")

    try:
        user = User.objects.get(profile__contact=phone)
    except User.DoesNotExist:
        messages.error(request, "No user found with this phone number.")
        return redirect("reset_with_phone")

    # Delete old OTPs
    PasswordResetOTP.objects.filter(user=user).delete()

    # Generate new OTP
    new_otp = PasswordResetOTP.generate_otp()
    PasswordResetOTP.objects.create(user=user, otp=new_otp)

    # Send via Twilio or fallback
    send_otp(phone, new_otp)

    messages.success(request, f"A new OTP has been sent to {phone}.")
    return redirect("verify_otp")


