"""Old addresses that moved: links shared over the years and search engines land on the new ones."""
from django.http import HttpResponsePermanentRedirect
from django.urls import reverse


class HttpResponsePermanentRedirectKeepMethod(HttpResponsePermanentRedirect):
    status_code = 308  # a POST to an old address stays a POST


def moved(name):
    """A view that sends to the route `name`, with the same captured values and the same query string."""
    def view(request, *args, **kwargs):
        url = reverse(name, args=args, kwargs=kwargs)
        if request.META.get("QUERY_STRING"):
            url += "?" + request.META["QUERY_STRING"]
        if request.method in ("GET", "HEAD"):
            return HttpResponsePermanentRedirect(url)
        return HttpResponsePermanentRedirectKeepMethod(url)
    return view
