"""The search index is shared by everyone: only what anyone may see goes in."""
from haystack import indexes


class PublicOnlyIndexMixin(object):
    """Index an object only while it is public, and drop it when it stops being so."""

    def is_public(self, obj):
        raise NotImplementedError

    def update_object(self, instance, using=None, **kwargs):
        if self.is_public(instance):
            return super().update_object(instance, using=using, **kwargs)
        return self.remove_object(instance, using=using, **kwargs)


def reindex(instances):
    """Refresh the search entries of these objects after their visibility changed."""
    try:
        from haystack import connections
        unified = connections['default'].get_unified_index()
        for obj in instances:
            index = unified.get_index(type(obj))
            index.update_object(obj)
    except Exception:  # search is a convenience; never break a save because of it
        import logging
        logging.getLogger(__name__).exception("reindex failed")
