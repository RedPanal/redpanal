import datetime
from haystack import indexes
from redpanal.utils.search import PublicOnlyIndexMixin
from .models import Audio


class AudioIndex(PublicOnlyIndexMixin, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    author = indexes.CharField(model_attr='user')
    created_at = indexes.DateTimeField(model_attr='created_at')
    tags = indexes.MultiValueField()

    def prepare_tags(self, obj):
        return [tag.name for tag in obj.tags.all()]

    def get_model(self):
        return Audio

    def is_public(self, obj):
        # A part of a work is indexed through the work, once it's known to be public.
        if getattr(obj, "_part_of_work", False):
            return False
        return Audio.objects.visible_to(None).filter(pk=obj.pk).exists()

    def index_queryset(self, using=None):
        return self.get_model().objects.visible_to(None)
