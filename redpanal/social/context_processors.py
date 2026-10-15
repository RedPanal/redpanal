def notifications(request):
    """How many notifications are waiting, for the bell in the header."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"unread_notifications": user.notifications.filter(read_at__isnull=True).count()}
