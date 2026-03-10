import datetime
from haystack import indexes
from .models import UserProfile


class UserProfileIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)

    def prepare_tags(self, obj):
        return [tag.name for tag in obj.tags.all()]

    def get_model(self):
        return UserProfile

    def index_queryset(self, using=None):
        return self.get_model().objects.all()
