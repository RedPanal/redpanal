# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About RedPanal

RedPanal is a collaborative music platform built with Django. It allows musicians to upload, share, remix, and collaborate on audio tracks and music projects. The live site is at redpanal.org.

## Commands

All Django commands must be run from the `redpanal/` subdirectory (where `manage.py` lives):

```bash
cd redpanal

# Run development server
python manage.py runserver

# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test audio
python manage.py test project
python manage.py test social

# Run migrations
python manage.py migrate --fake-initial

# Create migrations after model changes
python manage.py makemigrations
```

### System dependencies
`ffmpeg` and `libavcodec-extra` are required for audio processing (pydub uses ffmpeg under the hood).

## Architecture

### Project layout

```
redpanal-master/
└── redpanal/           # Django project root (contains manage.py)
    ├── redpanal/       # Main Django settings package
    │   ├── settings.py         # Dev settings (SQLite, DEBUG=True)
    │   ├── common_settings.py  # Shared settings across environments
    │   ├── urls.py             # Root URL configuration
    │   └── api.py              # REST API endpoints (DRF)
    ├── audio/          # Audio upload/management app
    ├── project/        # Collaborative music projects app
    ├── core/           # Shared utilities, licenses, hashtag views
    ├── social/         # Messaging, activity feed, @mentions, #hashtags
    └── users/          # User profiles, authentication adapters
```

### Core data model

- **Audio**: uploaded audio files with genre/instrument/type metadata, geolocation, waveform generation, and SHA1 hashsum. On save, `pydub` processes the file to extract metadata and generate waveform PNG images.
- **Project**: a collection of Audio objects. Supports versioning (`version_of` self-FK) and audio mixing (overlays multiple tracks into an OGG file cached by hashsum).
- **Message** (`social` app): freeform text with `@mention` and `#hashtag` parsing, linked to any object via GenericForeignKey. The rendered HTML is cached in `_msg_html_cache`.

### Key design patterns

- All content models use `django-taggit` for hashtag support and `django-autoslug` for URL slugs.
- Activity feed uses `django-activity-stream` — Audio, Project, and Message creation emit signals to the stream.
- Search uses `django-haystack` with the Whoosh backend; each app has a `search_indexes.py`.
- The REST API (`/api/`) is in `redpanal/api.py` using Django REST Framework. It exposes Audio CRUD plus filtered listing endpoints.
- Authentication uses `django-allauth` with Google and Twitter social providers. Custom signup/login forms are in `redpanal/forms.py`.
- Settings are split: `common_settings.py` holds shared config; `settings.py` is the dev override (SQLite, DEBUG=True, CORS allow all).

### URL structure

| Prefix | App |
|--------|-----|
| `/a/` | audio |
| `/p/` | project |
| `/u/` | users |
| `/tag/<slug>/` | core (hashtag lists) |
| `/activity/` | social + actstream |
| `/api/` | REST API |
| `/accounts/` | allauth |

### Audio processing flow

When an `Audio` instance is saved with a new file, the `audio_created_signal` post-save handler calls `audio_processing()`, which:
1. Decodes the file with `pydub`
2. Generates two waveform PNGs (460px and 940px wide) alongside the audio file
3. Stores `channels`, `samplerate`, `totalframes`, and `hashsum` on the model

Uploaded media goes to `../uploaded_media/` relative to the project root (configurable via `MEDIA_ROOT`).
