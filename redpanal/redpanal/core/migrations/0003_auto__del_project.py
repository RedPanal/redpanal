# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting model 'Project'
        db.delete_table(u'core_project')

        # Removing M2M table for field audios on 'Project'
        db.delete_table(db.shorten_name(u'core_project_audios'))


    def backwards(self, orm):
        # Adding model 'Project'
        db.create_table(u'core_project', (
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('slug', self.gf('autoslug.fields.AutoSlugField')(max_length=50, unique_with=(), unique=True, populate_from='name', blank=True)),
            ('description', self.gf('django.db.models.fields.TextField')()),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100, unique=True)),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('version_of', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['core.Project'], null=True, blank=True)),
        ))
        db.send_create_signal(u'core', ['Project'])

        # Adding M2M table for field audios on 'Project'
        m2m_table_name = db.shorten_name(u'core_project_audios')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('project', models.ForeignKey(orm[u'core.project'], null=False)),
            ('audio', models.ForeignKey(orm[u'audio.audio'], null=False))
        ))
        db.create_unique(m2m_table_name, ['project_id', 'audio_id'])


    models = {
        
    }

    complete_apps = ['core']