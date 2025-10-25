from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Song, AudioFile, LANGUAGE_CHOICES, UserProfile

User = get_user_model()


class SongForm(forms.ModelForm):
    """Form for creating/editing songs with multilingual support"""
    
    # Optional YouTube URL field (not in model directly)
    youtube_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            "class": "w-full border border-amber-300 rounded-md p-2",
            "placeholder": "https://www.youtube.com/watch?v=..."
        }),
        help_text="Provide YouTube URL to download audio automatically"
    )
    
    # Optional direct audio upload
    audio_upload = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            "class": "w-full border border-amber-300 rounded-md p-2",
            "accept": "audio/*"
        }),
        help_text="Or upload an audio file directly"
    )
    
    class Meta:
        model = Song
        fields = [
            "language",
            "title_ta", "title_te", "title_en",
            "lyrics_ta", "lyrics_te", "lyrics_en",
            "cover_image", "is_favorite"
        ]
        widgets = {
            "language": forms.Select(attrs={"class": "w-full border border-amber-300 rounded-md p-2"}),
            "title_ta": forms.TextInput(attrs={"class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "Tamil title"}),
            "title_te": forms.TextInput(attrs={"class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "Telugu title"}),
            "title_en": forms.TextInput(attrs={"class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "English title"}),
            "lyrics_ta": forms.Textarea(attrs={"rows": 8, "class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "Tamil lyrics (optional)"}),
            "lyrics_te": forms.Textarea(attrs={"rows": 8, "class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "Telugu lyrics (optional)"}),
            "lyrics_en": forms.Textarea(attrs={"rows": 8, "class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "English lyrics (optional)"}),
            "cover_image": forms.FileInput(attrs={"class": "w-full border border-amber-300 rounded-md p-2", "accept": "image/*"}),
            "is_favorite": forms.CheckboxInput(attrs={"class": "rounded"}),
        }
        labels = {
            "title_ta": "Tamil Title",
            "title_te": "Telugu Title",
            "title_en": "English Title",
            "lyrics_ta": "Tamil Lyrics",
            "lyrics_te": "Telugu Lyrics",
            "lyrics_en": "English Lyrics",
            "is_favorite": "Mark as Favorite",
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # At least one title must be provided
        if not any([cleaned_data.get('title_ta'), cleaned_data.get('title_te'), cleaned_data.get('title_en')]):
            raise forms.ValidationError("At least one title (Tamil, Telugu, or English) is required.")
        
        # Audio is now optional - no validation needed
        
        return cleaned_data


class AddLanguageVersionForm(forms.Form):
    """Form for adding a new language version to existing song"""
    
    language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        widget=forms.Select(attrs={"class": "w-full border border-amber-300 rounded-md p-2"})
    )
    
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "Song title in selected language"}),
        label="Title"
    )
    
    lyrics = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 10, "class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "Lyrics in selected language"}),
        label="Lyrics"
    )
    
    def __init__(self, *args, song=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter out languages that already exist for this song
        if song:
            available_langs = [lang[0] for lang in song.available_languages()]
            remaining_choices = [(code, name) for code, name in LANGUAGE_CHOICES if code not in available_langs]
            self.fields['language'].choices = remaining_choices
            
            if not remaining_choices:
                self.fields['language'].widget.attrs['disabled'] = True
                self.fields['language'].help_text = "All languages are already added for this song."


class EnhancedUserRegistrationForm(UserCreationForm):
    """Enhanced registration with region and language preferences"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "your@email.com"})
    )
    
    language_preference = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        initial="tamil",
        widget=forms.Select(attrs={"class": "w-full border border-amber-300 rounded-md p-2"}),
        label="Preferred Language"
    )
    
    region = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "e.g., Tamil Nadu, Andhra Pradesh"}),
        label="Region/State"
    )
    
    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "Your city"}),
        label="City"
    )
    
    contact = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "w-full border border-amber-300 rounded-md p-2", "placeholder": "+91 1234567890"}),
        label="Contact Number"
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={"class": "w-full border border-amber-300 rounded-md p-2"}),
        }
    
    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            UserProfile.objects.create(
                user=user,
                language_preference=self.cleaned_data['language_preference'],
                region=self.cleaned_data['region'],
                city=self.cleaned_data['city'],
                contact=self.cleaned_data['contact']
            )
        return user
