from django.contrib.auth.models import User, Group
from audio.models import Audio
from rest_framework import routers, serializers, viewsets

class AudioSerializer(serializers.HyperlinkedModelSerializer):
    # specifying manualy a list field for tags to access the method get_tags
    # but maintain the 'tags' name of the field.
    tags = serializers.ListField(source='get_tags')

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

api_router = routers.DefaultRouter()
api_router.register(r'audio', AudioViewSet, base_name='audio-api')
