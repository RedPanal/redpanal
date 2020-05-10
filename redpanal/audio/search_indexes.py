import datetime
from haystack import indexes
from .models import Audio


class AudioIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    author = indexes.CharField(model_attr='user')
    created_at = indexes.DateTimeField(model_attr='created_at')
    tags = indexes.MultiValueField()

    def prepare_tags(self, obj):
        return [tag.name for tag in obj.tags.all()]

    def get_model(self):
        return Audio

    def index_queryset(self, using=None):
        return self.get_model().objects.all()
