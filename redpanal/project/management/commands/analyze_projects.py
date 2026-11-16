from django.core.management.base import BaseCommand

from project.models import Project
from audio.models import Audio
from actstream.models import Action


class Command(BaseCommand):
    help = 'Analyze Project data to inform the Project→Mix refactor'

    def handle(self, *args, **options):
        total = Project.objects.count()
        with_audios = Project.objects.filter(audios__isnull=False).distinct().count()
        versions = Project.objects.filter(version_of__isnull=False).count()
        audios_in_projects = Audio.objects.filter(project__isnull=False).distinct().count()
        actstream_created = Action.objects.filter(verb='project_created').count()

        self.stdout.write('\n=== Project data report ===\n')
        self.stdout.write(f'  Total projects:                      {total}')
        self.stdout.write(f'  Projects with at least one audio:    {with_audios}')
        self.stdout.write(f'  Projects that are versions of other: {versions}')
        self.stdout.write(f'  Audios linked to at least one project: {audios_in_projects}')
        self.stdout.write(f'  Actstream actions "project_created": {actstream_created}')
        self.stdout.write('')
