import os

def get_file_extension(filename):
    return os.path.splitext(filename)[1][1:].lower()

def get_git_revision_short_hash():
    import subprocess
    try:
        short_hash = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                                    capture_output=True).stdout.strip().decode()
    except:
        short_hash = ""
    return short_hash

def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


def safe_next(request, *candidates, default="/"):
    """Where to go back after a form: the first candidate that stays on this site.

    `next` and `Referer` come from the browser: without this check, a link could send someone
    from a RedPanal page to any other site (open redirect).
    """
    from django.utils.http import url_has_allowed_host_and_scheme
    for url in candidates:
        if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()},
                                                   require_https=request.is_secure()):
            return url
    return default


def back(request, default="/"):
    """`next` from the form, else the page it came from, else `default`: only addresses on this site."""
    return safe_next(request, request.POST.get("next"), request.GET.get("next"),
                     request.META.get("HTTP_REFERER"), default=default)
