from django.contrib.auth.models import User, Group
from audio.models import Audio
from rest_framework import routers, serializers, viewsets
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
        )

class AudioViewSet(viewsets.ModelViewSet):
    queryset = Audio.objects.all().order_by('-created_at')
    serializer_class = AudioSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


api_router = routers.DefaultRouter()
api_router.register(r'audio', AudioViewSet, base_name='audio-api')
