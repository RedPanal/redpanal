import datetime
from haystack import indexes
from redpanal.utils.search import PublicOnlyIndexMixin
from .models import Message, visible_messages


class MessageIndex(PublicOnlyIndexMixin, indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    author = indexes.CharField(model_attr='user')
    created_at = indexes.DateTimeField(model_attr='created_at')
    tags = indexes.MultiValueField()

    def prepare_tags(self, obj):
        return [tag.name for tag in obj.tags.all()]

    def get_model(self):
        return Message

    def is_public(self, obj):
        return visible_messages(Message.objects.filter(pk=obj.pk), None).exists()

    def index_queryset(self, using=None):
        """Used when the entire index for model is updated."""
        return visible_messages(self.get_model().objects.all(), None)
