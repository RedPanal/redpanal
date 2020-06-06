from django.contrib.auth.models import User, Group
from django.conf.urls import include, url
from audio.models import Audio
from rest_framework import routers, serializers, viewsets, generics, pagination
from rest_framework.decorators import action
from rest_framework.response import Response
from taggit_serializer.serializers import (TagListSerializerField,
                                           TaggitSerializer)


class AdjustableResultsSetPagination(pagination.PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 10000


class AudioSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField()
    class Meta:
        model = Audio
        fields = (
            'id', 'slug', 'name', 'audio', 'user', 'created_at', 'license',
            'description', 'totalframes', 'samplerate',
            'use_type', 'genre', 'instrument', 'tags',
            'position_lat', 'position_long',
        )


class AudioViewSet(viewsets.ModelViewSet):
    queryset = Audio.objects.all().order_by('-created_at')
    serializer_class = AudioSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AudioList(generics.ListAPIView):
    """
    List audios. Query parameters can be used to filter the list.
    Eg: audio/list/?user=redpanal&genre=rock&tag=awesome

    Query parameters: [user, genre, instrument, use_type, tag]
    Note that tag can be provided multiple times no narrow more the list (Eg /?tag=foo&tag=bar)
    """
    serializer_class = AudioSerializer
    pagination_class = AdjustableResultsSetPagination

    def get_queryset(self):
        queryset = Audio.objects.all()

        filter_data = {}
        username = self.request.query_params.get('user', None)
        if username is not None:
            filter_data['user__username'] = username

        for filter_param in ['genre', 'instrument', 'use_type']:
            param = self.request.query_params.get(filter_param, None)
            if param is not None:
                filter_data[filter_param] = param

        queryset = queryset.filter(**filter_data)

        tags = self.request.query_params.getlist('tag')
        for tag in tags:
            queryset = queryset.filter(tags__slug=tag)

        if self.request.query_params.getlist('positioned', None):
            queryset = queryset.exclude(position_long__isnull=True, position_lat__isnull=True)

        return queryset.order_by('-created_at')

api_router = routers.DefaultRouter()
api_router.register(r'audio', AudioViewSet, basename='audio-api')

api_urls = [
    url('^audio/list/$', AudioList.as_view()),
] + api_router.urls
