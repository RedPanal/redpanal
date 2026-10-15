from .models import PALETTE_CHOICES, PALETTE_DEFAULT

# The browser's bar takes the palette's page color.
THEME_COLORS = {"moderna": "#1b2a34", "neon": "#12181e", "calida": "#252525", "lavanda": "#2f2a45"}


def palette(request):
    """The colors this person chose in their settings; without an account, the default ones."""
    key = PALETTE_DEFAULT
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        chosen = getattr(getattr(user, "userprofile", None), "palette", "")
        if chosen in dict(PALETTE_CHOICES):
            key = chosen
    return {"palette": key, "palette_is_dark": key == "neon", "palette_theme_color": THEME_COLORS[key]}
