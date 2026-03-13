from django.contrib.auth import authenticate
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.shortcuts import get_object_or_404
from django.urls import path, re_path
from audio.models import Audio
from social.models import Message
from actstream.models import actor_stream, user_stream
from rest_framework import routers, serializers, viewsets, generics, pagination
from rest_framework.filters import SearchFilter
from rest_framework.authentication import BaseAuthentication
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from taggit_serializer.serializers import (TagListSerializerField,
                                           TaggitSerializer)
from avatar.utils import get_primary_avatar

_TOKEN_SALT = 'redpanal-spa-auth'
_TOKEN_MAX_AGE = 30 * 24 * 3600  # 30 days


class SignedTokenAuthentication(BaseAuthentication):
    """
    Stateless token auth via Django's signing framework.
    No DB table needed — tokens are signed with SECRET_KEY.
    Frontend sends: Authorization: Bearer <token>
    """
    def authenticate(self, request):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith('Bearer '):
            return None
        token = auth[7:].strip()
        try:
            data = signing.loads(token, salt=_TOKEN_SALT, max_age=_TOKEN_MAX_AGE)
            user = User.objects.get(id=data['user_id'])
            return (user, token)
        except signing.SignatureExpired:
            raise AuthenticationFailed('Token expirado')
        except Exception:
            raise AuthenticationFailed('Token inválido')

    def authenticate_header(self, request):
        return 'Bearer'


class AdjustableResultsSetPagination(pagination.PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 10000


class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'avatar_url')
        read_only_fields = ('id', 'username', 'avatar_url')

    def get_avatar_url(self, obj):
        avatar = get_primary_avatar(obj)
        if avatar:
            return avatar.avatar_url(80)
        return None


class AudioSerializer(TaggitSerializer, serializers.ModelSerializer):
    tags = TagListSerializerField()
    user = UserSerializer(read_only=True)
    # user_id is only used if a client needs to specify the user explicitly.
    # perform_create() always overrides it with request.user, so not required.
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True, required=False
    )
    # Model fields that have no blank=True but are optional from the SPA's perspective.
    description = serializers.CharField(required=False, allow_blank=True, default='')
    genre       = serializers.CharField(required=False, allow_blank=True, default='')
    instrument  = serializers.CharField(required=False, allow_blank=True, default='')
    source_audio_id = serializers.PrimaryKeyRelatedField(
        queryset=Audio.objects.all(), source='source_audio', write_only=True,
        required=False, allow_null=True,
    )

    class Meta:
        model = Audio
        fields = (
            'id', 'slug', 'name', 'audio', 'user', 'user_id', 'created_at', 'license',
            'description', 'totalframes', 'samplerate',
            'use_type', 'genre', 'instrument', 'tags',
            'position_lat', 'position_long', 'source_audio_id',
        )


class AudioViewSet(viewsets.ModelViewSet):
    queryset = Audio.objects.all().order_by('-created_at')
    serializer_class = AudioSerializer
    authentication_classes = [SignedTokenAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AudioList(generics.ListAPIView):
    """
    List audios. Query parameters can be used to filter the list.
    Eg: audio/list/?user=redpanal&genre=rock&tag=awesome

    Query parameters: [user, genre, instrument, use_type, tag, search]
    Note that tag can be provided multiple times no narrow more the list (Eg /?tag=foo&tag=bar)
    """
    serializer_class = AudioSerializer
    pagination_class = AdjustableResultsSetPagination
    authentication_classes = [SignedTokenAuthentication]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'description', 'tags__name', 'user__username']

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

        _SAFE_ORDERINGS = {'-created_at', '-id'}
        ordering = self.request.query_params.get('ordering', '-created_at')
        if ordering not in _SAFE_ORDERINGS:
            ordering = '-created_at'
        return queryset.order_by(ordering)


class AudioBySlugView(generics.RetrieveAPIView):
    queryset = Audio.objects.all()
    lookup_field = 'slug'
    serializer_class = AudioSerializer
    authentication_classes = [SignedTokenAuthentication]


# ── User stats endpoint ───────────────────────────────────────────────────────

@api_view(['GET'])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([AllowAny])
def user_stats(request, username):
    """Return follower/following counts for a user profile."""
    from actstream.models import followers, following as actstream_following
    user = get_object_or_404(User, username=username)
    return Response({
        'username': user.username,
        'followers_count': len(followers(user)),
        'following_count': len(actstream_following(user)),
    })


# ── Auth JSON endpoints ───────────────────────────────────────────────────────

def _user_response(user):
    avatar = get_primary_avatar(user)
    return {
        'id': user.id,
        'username': user.username,
        'avatar_url': avatar.avatar_url(80) if avatar else None,
    }


@api_view(['GET'])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([AllowAny])
def auth_me(request):
    """Return the currently authenticated user or 401."""
    if request.user.is_authenticated:
        return Response(_user_response(request.user))
    return Response(None, status=401)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def auth_login_view(request):
    """Authenticate and return a signed Bearer token. No session, no CSRF."""
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')
    if not username or not password:
        return Response({'error': 'Usuario y contraseña requeridos'}, status=400)
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'error': 'Credenciales incorrectas'}, status=400)
    token = signing.dumps({'user_id': user.id}, salt=_TOKEN_SALT)
    return Response({'token': token, **_user_response(user)})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def auth_logout_view(request):
    """Stateless logout: client just discards the token."""
    return Response({'ok': True})


# ── Activity endpoints ────────────────────────────────────────────────────────

def _serialize_action(a):
    """Serialize an actstream Action to the agreed JSON shape."""
    actor_obj = a.actor
    avatar = get_primary_avatar(actor_obj) if actor_obj else None

    # Resolve action_object type + fields
    ao = a.action_object
    ao_type = None
    ao_data = None
    if ao is not None:
        ct = ContentType.objects.get_for_model(ao)
        ao_type = ct.model  # e.g. 'audio', 'project', 'message'
        if ao_type == 'audio':
            ao_data = {'slug': ao.slug, 'name': ao.name}
        elif ao_type == 'project':
            ao_data = {'slug': getattr(ao, 'slug', None), 'name': str(ao)}
        else:
            ao_data = {'name': str(ao)}

    return {
        'id': a.pk,
        'verb': a.verb,
        'actor': {
            'username': actor_obj.username if actor_obj else None,
            'avatar_url': avatar.avatar_url(80) if avatar else None,
        },
        'action_object_type': ao_type,
        'action_object': ao_data,
        'timestamp': a.timestamp.isoformat().replace('+00:00', 'Z'),
    }


@api_view(['GET'])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([AllowAny])
def activity_global(request):
    """Latest public actions across all users — no auth required."""
    from actstream.models import Action as ActstreamAction
    qs = ActstreamAction.objects.filter(public=True).order_by('-timestamp')[:20]
    return Response([_serialize_action(a) for a in qs])


@api_view(['GET'])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([IsAuthenticated])
def activity_me(request):
    """Actions performed by the logged-in user (actor_stream)."""
    actions_qs = actor_stream(request.user).select_related(
        'actor_content_type', 'action_object_content_type', 'target_content_type'
    )[:50]
    return Response([_serialize_action(a) for a in actions_qs])


@api_view(['GET'])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([IsAuthenticated])
def activity_feed(request):
    """Activity feed of users the logged-in user follows (user_stream)."""
    actions_qs = user_stream(request.user).select_related(
        'actor_content_type', 'action_object_content_type', 'target_content_type'
    )[:50]
    return Response([_serialize_action(a) for a in actions_qs])


class MessageSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    msg_html = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ('id', 'msg_html', 'user', 'created_at')

    def get_msg_html(self, obj):
        return obj.as_html()


def _build_audio_tree(audio, depth=0, max_depth=5, request=None):
    if audio.audio:
        raw_url = audio.audio.url
        audio_url = request.build_absolute_uri(raw_url) if request else raw_url
    else:
        audio_url = None
    node = {
        'id': audio.id,
        'slug': audio.slug,
        'name': audio.name,
        'audio': audio_url,
        'user': UserSerializer(audio.user).data,
        'use_type': audio.use_type,
        'collaborations': [],
    }
    if depth < max_depth:
        for child in audio.collaborations.select_related('user').order_by('created_at'):
            node['collaborations'].append(_build_audio_tree(child, depth + 1, max_depth, request=request))
    return node


class AudioCollabTreeView(APIView):
    authentication_classes = [SignedTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, slug):
        audio = get_object_or_404(Audio.objects.select_related('source_audio', 'user'), slug=slug)
        # Walk up to find the root of the collaboration tree
        root = audio
        visited = {audio.pk}
        while root.source_audio_id is not None:
            if root.source_audio_id in visited:
                break  # cycle guard
            visited.add(root.pk)
            root = Audio.objects.select_related('source_audio', 'user').get(pk=root.source_audio_id)
        return Response(_build_audio_tree(root, request=request))


class AudioCommentsView(APIView):
    authentication_classes = [SignedTokenAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, slug):
        audio = get_object_or_404(Audio, slug=slug)
        ct = ContentType.objects.get_for_model(Audio)
        comments = Message.objects.filter(
            content_type=ct, object_id=audio.pk
        ).order_by('created_at')
        return Response(MessageSerializer(comments, many=True).data)

    def post(self, request, slug):
        audio = get_object_or_404(Audio, slug=slug)
        msg_text = request.data.get('msg', '').strip()
        if not msg_text:
            return Response({'error': 'msg is required'}, status=400)
        ct = ContentType.objects.get_for_model(Audio)
        msg = Message(
            msg=msg_text,
            user=request.user,
            content_type=ct,
            object_id=audio.pk,
        )
        msg.save()
        return Response(MessageSerializer(msg).data, status=201)


@api_view(['GET'])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([IsAuthenticated])
def my_following(request):
    """Return list of usernames the current user follows."""
    from actstream.models import following as actstream_following
    followed_users = actstream_following(request.user, User)
    return Response([u.username for u in followed_users])


@api_view(['POST', 'DELETE'])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([IsAuthenticated])
def user_follow(request, username):
    """Follow (POST) or unfollow (DELETE) a user by username."""
    from actstream import actions
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return Response({'error': 'No podés seguirte a vos mismo'}, status=400)
    if request.method == 'POST':
        from django.db import IntegrityError
        try:
            actions.follow(request.user, target, send_action=False, actor_only=True)
        except IntegrityError:
            pass  # already following — idempotent
        return Response({'following': True}, status=201)
    else:
        actions.unfollow(request.user, target)
        return Response({'following': False}, status=200)


@api_view(['GET'])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([AllowAny])
def tags_popular(request):
    """Top tags by usage count. ?limit=N (default 20, max 50)."""
    from taggit.models import Tag
    from django.db.models import Count
    limit = min(int(request.query_params.get('limit', 20)), 50)
    tags = (
        Tag.objects
        .annotate(n=Count('taggit_taggeditem_items'))
        .filter(n__gt=0)
        .order_by('-n')[:limit]
    )
    return Response([{'name': t.name, 'slug': t.slug, 'count': t.n} for t in tags])


api_router = routers.DefaultRouter()
api_router.register(r'audio', AudioViewSet, basename='audio-api')

api_urls = [
    path('auth/me/', auth_me),
    path('auth/login/', auth_login_view),
    path('auth/logout/', auth_logout_view),
    path('audio/list/', AudioList.as_view()),
    re_path(r'^audio/(?P<slug>[\w-]+)/collab-tree/$', AudioCollabTreeView.as_view()),
    re_path(r'^audio/(?P<slug>[\w-]+)/comments/$', AudioCommentsView.as_view()),
    re_path('^audio/by-slug/(?P<slug>[\w-]+)/?$', AudioBySlugView.as_view()),
    path('users/<str:username>/stats/', user_stats),
    path('users/following/me/', my_following),
    path('users/<str:username>/follow/', user_follow),
    path('tags/popular/', tags_popular),
    path('activity/global/', activity_global),
    path('activity/me/', activity_me),
    path('activity/feed/', activity_feed),
] + api_router.urls
