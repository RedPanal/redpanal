from django.urls import path, re_path

from redpanal.utils.redirects import moved
from . import views


urlpatterns = [
    # Old addresses: creating is /crear/, browsing is /explorar/.
    path('create/', moved('create')),
    path('list/', moved('explore')),
    re_path(r'^(?P<slug>[\w-]+)/$', views.project_detail, name='project-detail'),
    re_path(r'^(?P<slug>[\w-]+)/editar/$', views.ProjectUpdateView.as_view(), name='project-edit'),
    re_path(r'^(?P<slug>[\w-]+)/borrar/$', views.ProjectDeleteView.as_view(), name='project-delete'),
    re_path(r'^(?P<slug>[\w-]+)/bajar-mezcla/$', views.download_mix, name='project-download-mix'),
    re_path(r'^(?P<slug>[\w-]+)/aportar/$', views.contribute, name='project-contribute'),
    re_path(r'^(?P<slug>[\w-]+)/aportes/(?P<pk>\d+)/estado/$', views.contribution_status,
            name='contribution-status'),
    re_path(r'^(?P<slug>[\w-]+)/aportes/(?P<pk>\d+)/alinear/$', views.contribution_align,
            name='contribution-align'),
    re_path(r'^(?P<slug>[\w-]+)/versiones/nueva/$', views.version_create, name='project-version-create'),
    re_path(r'^(?P<slug>[\w-]+)/v/(?P<number>\d+)/$', views.version_detail, name='project-version'),
    re_path(r'^(?P<slug>[\w-]+)/v/(?P<number>\d+)/volver/$', views.version_restore, name='project-version-restore'),
    re_path(r'^(?P<slug>[\w-]+)/v/(?P<number>\d+)/ocultar/$', views.version_hide, name='project-version-hide'),
    re_path(r'^(?P<slug>[\w-]+)/v/(?P<number>\d+)/mezcla\.mp3$', views.version_mix, name='project-version-mix'),
    re_path(r'^(?P<slug>[\w-]+)/pedidos/nuevo/$', views.request_create, name='project-request-create'),
    re_path(r'^(?P<slug>[\w-]+)/pedidos/(?P<pk>\d+)/alternar/$', views.request_toggle,
            name='project-request-toggle'),
    re_path(r'^(?P<slug>[\w-]+)/comentar/$', views.comment_create, name='project-comment'),
    re_path(r'^(?P<slug>[\w-]+)/seguir/$', views.project_follow, name='project-follow'),
    re_path(r'^(?P<slug>[\w-]+)/creditos\.txt$', views.credits_export, name='project-credits'),
    re_path(r'^(?P<slug>[\w-]+)/partes\.zip$', views.parts_zip, name='project-parts-zip'),
    re_path(r'^(?P<slug>[\w-]+)/comprobante/$', views.certificate, name='project-certificate'),
    re_path(r'^(?P<slug>[\w-]+)/carpeta/$', views.stems_upload, name='project-stems'),
    re_path(r'^(?P<slug>[\w-]+)/archivos/(?P<pk>\d+)/$', views.attachment_download, name='project-attachment'),
    re_path(r'^(?P<slug>[\w-]+)/ajustes/$', views.project_settings, name='project-settings'),
    re_path(r'^(?P<slug>[\w-]+)/acceso/$', views.visibility_update, name='project-visibility'),
    re_path(r'^(?P<slug>[\w-]+)/acceso/invitar/$', views.member_invite, name='project-invite'),
    re_path(r'^(?P<slug>[\w-]+)/acceso/(?P<pk>\d+)/$', views.member_decide, name='project-member-decide'),
    re_path(r'^(?P<slug>[\w-]+)/acceso/pedir/$', views.access_request, name='project-access-request'),
    re_path(r'^(?P<slug>[\w-]+)/acceso/unirme/$', views.join_by_link, name='project-join'),
    # Old addresses.
    re_path(r'^(?P<slug>[\w-]+)/edit/$', moved('project-edit')),
    re_path(r'^(?P<slug>[\w-]+)/delete/$', moved('project-delete')),
    re_path(r'^(?P<slug>[\w-]+)/create-version/$', moved('project-version-create')),
    re_path(r'^(?P<slug>[\w-]+)/download-mix/$', moved('project-download-mix')),
]
