from django.contrib.auth.models import User, Group
from audio.models import Audio
from rest_framework import routers, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from taggit_serializer.serializers import (TagListSerializerField,
                                           TaggitSerializer)


class AudioSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField()
    class Meta:
        model = Audio
        fields = (
            'id', 'slug', 'name', 'audio', 'created_at', 'license',
            'description', 'totalframes', 'samplerate',
            'use_type', 'genre', 'instrument', 'tags',
            'position_lat', 'position_long',
        )


class AudioViewSet(viewsets.ModelViewSet):
    queryset = Audio.objects.all().order_by('-created_at')
    serializer_class = AudioSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False)
    def positioned(self, request):
        audios = Audio.objects.exclude(position_long__isnull=True,
                                       position_lat__isnull=True).order_by('-created_at')

        page = self.paginate_queryset(audios)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(audios, many=True)
        return Response(serializer.data)


api_router = routers.DefaultRouter()
api_router.register(r'audio', AudioViewSet, basename='audio-api')

api_urls = api_router.urls
