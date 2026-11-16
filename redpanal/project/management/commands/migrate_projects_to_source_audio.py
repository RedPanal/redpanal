from django.core.management.base import BaseCommand

from project.models import Project
from audio.models import Audio


class Command(BaseCommand):
    help = (
        'Dry-run (default) or apply: set source_audio on Audio objects '
        'based on Project.version_of relationships.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually write changes. Without this flag runs as dry-run.',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        dry_run = not apply

        if dry_run:
            self.stdout.write('\n=== DRY RUN — no changes will be made ===\n')
        else:
            self.stdout.write('\n=== APPLYING CHANGES ===\n')

        # All version projects (those that are a version of another project)
        version_projects = (
            Project.objects
            .filter(version_of__isnull=False)
            .select_related('version_of', 'user')
            .prefetch_related('audios', 'version_of__audios')
            .order_by('created_at')
        )

        self.stdout.write(f'Version projects found: {version_projects.count()}\n')

        total_candidates = 0
        already_set = 0
        would_set = 0
        no_parent_audio = 0

        for vp in version_projects:
            parent = vp.version_of
            parent_audios = list(parent.audios.order_by('created_at'))
            version_audios = list(vp.audios.order_by('created_at'))

            if not parent_audios:
                self.stdout.write(
                    f'\n  [{vp.pk}] "{vp.name}" → version of [{parent.pk}] "{parent.name}"'
                )
                self.stdout.write(
                    f'       Parent has NO audios — {len(version_audios)} version audios left unlinked'
                )
                no_parent_audio += len(version_audios)
                continue

            # Representative source: oldest audio in the parent project
            representative = parent_audios[0]

            self.stdout.write(
                f'\n  [{vp.pk}] "{vp.name}" (by @{vp.user.username})'
                f' → version of [{parent.pk}] "{parent.name}"'
            )
            self.stdout.write(
                f'       Parent audios: {len(parent_audios)}'
                f'  |  Version audios: {len(version_audios)}'
                f'  |  Representative source: [{representative.pk}] "{representative.name}"'
            )

            for audio in version_audios:
                total_candidates += 1
                if audio.source_audio_id is not None:
                    already_set += 1
                    self.stdout.write(
                        f'       SKIP  [{audio.pk}] "{audio.name}" '
                        f'(source_audio already set to [{audio.source_audio_id}])'
                    )
                    continue

                if audio.pk == representative.pk:
                    # The audio IS the representative (audio lives in both projects)
                    self.stdout.write(
                        f'       SKIP  [{audio.pk}] "{audio.name}" '
                        f'(same object as representative — would create self-loop)'
                    )
                    continue

                would_set += 1
                self.stdout.write(
                    f'       SET   [{audio.pk}] "{audio.name}" '
                    f'.source_audio → [{representative.pk}] "{representative.name}"'
                )

                if apply:
                    Audio.objects.filter(pk=audio.pk).update(source_audio=representative)

        self.stdout.write('\n── Summary ──')
        self.stdout.write(f'  Version projects:                  {version_projects.count()}')
        self.stdout.write(f'  Version audios inspected:          {total_candidates}')
        self.stdout.write(f'  Already had source_audio (skipped):{already_set}')
        self.stdout.write(f'  Would SET source_audio:            {would_set}')
        self.stdout.write(f'  No parent audio (left unlinked):   {no_parent_audio}')

        if dry_run:
            self.stdout.write('\nRun with --apply to execute.\n')
        else:
            self.stdout.write('\nDone.\n')
