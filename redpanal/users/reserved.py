"""People live at the root (redpanal.org/<username>/), so a username can't be the name of a page.

The first segment of every route counts automatically; the extra names are kept for pages that may come."""
import re

from django.urls import get_resolver

EXTRA = {
    "about", "acerca", "admin", "ajustes", "api", "app", "archivo", "archivos", "ayuda", "blog", "buscar", "comunidad",
    "contacto", "crear", "docs", "estudio", "explorar", "favicon.ico", "grupos", "help", "inicio", "login", "logout",
    "media", "moderacion", "notificaciones", "personas", "privacidad", "proyectos", "redpanal", "reproductor",
    "robots.txt", "sitemap.xml", "sonidos", "static", "settings", "sobre", "soporte", "terminos", "u", "p", "a",
    "usuarios", "www",
    # Studio and lab, in every language the site speaks (or may): kept for the workspace and experiments.
    "studio", "estudio", "lab", "labo", "laboratorio", "laboratory",
    # Language prefixes, for when English and Portuguese get their own addresses (/en/..., /pt/...).
    "es", "en", "pt",
}

_LITERAL = re.compile(r"^\^?([\w.-]+)/")


def route_names(patterns=None):
    """The literal first segment of each route at the root (explorar, grupos, p, u...), also inside includes
    mounted at the root (core's pages)."""
    names = set()
    for pattern in get_resolver().url_patterns if patterns is None else patterns:
        text = str(pattern.pattern)
        match = _LITERAL.match(text)
        if match:
            names.add(match.group(1))
        elif text in ("", "^") and hasattr(pattern, "url_patterns"):
            names |= route_names(pattern.url_patterns)
        elif re.match(r"^\^?[\w.-]+\$?$", text):  # a page without a slash: sw.js
            names.add(text.strip("^$"))
    return names


def reserved_usernames():
    return {n.lower() for n in route_names() | EXTRA}


def is_reserved(username):
    return (username or "").lower() in reserved_usernames()
