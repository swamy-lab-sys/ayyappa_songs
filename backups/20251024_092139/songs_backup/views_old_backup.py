from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseBadRequest
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages
from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from weasyprint import HTML, CSS
from .models import Song
from .forms import SongForm
import os, io, tempfile, shutil, zipfile, yt_dlp, requests


# 🕉 SONG LIST
@login_required(login_url="login")
def song_list(request):
    q = request.GET.get("q", "").strip()
    songs = Song.objects.all().order_by("-uploaded_at")
    if q:
        songs = songs.filter(
            title__icontains=q
        ) | songs.filter(
            script_tamil__icontains=q
        ) | songs.filter(
            script_telugu__icontains=q
        ) | songs.filter(
            script_english__icontains=q
        )
    paginator = Paginator(songs.distinct(), 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "songs/list.html", {"page_obj": page_obj, "q": q})


# ➕ ADD SONG
@login_required
def song_add(request):
    audio_dir = os.path.join(settings.MEDIA_ROOT, "audio_files")
    cover_dir = os.path.join(settings.MEDIA_ROOT, "covers")
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(cover_dir, exist_ok=True)

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        language = request.POST.get("language", "tamil")
        script_tamil = request.POST.get("script_tamil", "").strip()
        script_telugu = request.POST.get("script_telugu", "").strip()
        script_english = request.POST.get("script_english", "").strip()
        youtube_url = request.POST.get("youtube_url", "").strip()
        audio_file = request.FILES.get("audio")
        cover = request.FILES.get("cover")

        if not title:
            messages.error(request, "Song title is required.")
            return redirect("song_add")

        song = Song(
            title=title,
            language=language,
            script_tamil=script_tamil,
            script_telugu=script_telugu,
            script_english=script_english,
            owner=request.user,
        )

        # 🎵 YouTube download handling
        if youtube_url:
            if "youtu.be/" in youtube_url:
                video_id = youtube_url.split("/")[-1].split("?")[0]
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"

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
                    title_from_yt = info.get("title", "Ayyappa Bhajan")
                    thumbnail_url = info.get("thumbnail")

                mp3_path = next(
                    (os.path.join(temp_dir, f)
                     for f in os.listdir(temp_dir)
                     if f.lower().endswith(".mp3")),
                    None,
                )
                if not mp3_path:
                    raise Exception("Converted MP3 file not found.")

                safe_title = title_from_yt.replace("/", "_").replace("\\", "_").strip()
                with open(mp3_path, "rb") as f:
                    song.audio.save(f"{safe_title}.mp3", ContentFile(f.read()))

                if not cover and thumbnail_url:
                    response = requests.get(thumbnail_url, timeout=10)
                    if response.status_code == 200:
                        song.cover_image.save(f"{safe_title}.jpg", ContentFile(response.content))

                messages.success(request, f"✅ YouTube audio '{title_from_yt}' added successfully!")

            except Exception as e:
                messages.error(request, f"⚠️ YouTube download failed: {e}")
                return redirect("song_add")
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)

        elif audio_file:
            song.audio = audio_file
        else:
            messages.error(request, "Please upload an audio file or enter a YouTube URL.")
            return redirect("song_add")

        if cover:
            song.cover_image = cover

        song.save()
        messages.success(request, f"🎶 '{song.title}' added successfully!")
        return redirect("song_list")

    form = SongForm()
    return render(request, "songs/add.html", {"form": form})


# ✏️ EDIT SONG
@login_required
def song_edit(request, pk):
    song = get_object_or_404(Song, pk=pk, owner=request.user)
    if request.method == "POST":
        form = SongForm(request.POST, request.FILES, instance=song)
        if form.is_valid():
            form.save()
            messages.success(request, "Song updated successfully!")
            return redirect("song_list")
    else:
        form = SongForm(instance=song)
    return render(request, "songs/add.html", {"form": form, "edit_mode": True})


# ❌ DELETE SONG
@login_required
def song_delete(request, pk):
    song = get_object_or_404(Song, pk=pk, owner=request.user)
    song.delete()
    messages.warning(request, f"'{song.title}' was deleted successfully.")
    return redirect("song_list")


# 🎧 VIEW SONG DETAILS
def song_view(request, pk):
    song = get_object_or_404(Song, pk=pk)
    return render(request, "songs/view.html", {"song": song})


# 📄 DOWNLOAD SONG AS PDF
def song_download(request, pk):
    song = get_object_or_404(Song, pk=pk)
    html_string = render_to_string("songs/pdf_multilang.html", {"song": song})
    html = HTML(string=html_string, base_url=request.build_absolute_uri("/"))
    css = CSS(string="""
        @page {
            size: A4;
            margin: 1.5cm;
            background: linear-gradient(180deg, #fffdf8, #fffaf2);
            @bottom-center {
                content: "🕉 Swamiye Saranam Ayyappa • Page " counter(page);
                font-family: 'Cinzel', serif;
                font-size: 9pt;
                color: #7c2d12;
            }
        }
    """)
    pdf = html.write_pdf(stylesheets=[css])
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename=\"{song.title}_Ayyappa.pdf\"'
    return response


# 📦 BULK DOWNLOAD AS ZIP
def bulk_download(request):
    ids = request.GET.get("ids", "")
    if not ids:
        return HttpResponseBadRequest("No ids provided")

    id_list = [int(i) for i in ids.split(",") if i.isdigit()]
    songs = Song.objects.filter(id__in=id_list)
    mem = io.BytesIO()

    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in songs:
            if s.audio:
                try:
                    data = s.audio.read()
                    zf.writestr(s.audio.name.split("/")[-1], data)
                except Exception:
                    pass
            zf.writestr(f"{s.title}.txt",
                        (s.script_tamil or s.script_telugu or s.script_english or ""))

    mem.seek(0)
    resp = HttpResponse(mem.read(), content_type="application/zip")
    resp["Content-Disposition"] = 'attachment; filename="songs_bundle.zip"'
    return resp


# 👤 USER AUTH
def user_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("song_list")
        messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, "songs/login.html", {"form": form})


def user_logout(request):
    logout(request)
    return redirect("login")


def user_register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created successfully! Please log in below.")
            return redirect("login")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserCreationForm()
    return render(request, "songs/register.html", {"form": form})
