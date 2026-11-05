from django.core.management.base import BaseCommand
from django.db.models import Count
from taggit.models import Tag, TaggedItem


class Command(BaseCommand):
    help = 'Analyze and clean dirty tags (trailing commas, encoding issues, case duplicates)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually apply changes. Without this flag runs as dry-run.',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        dry_run = not apply

        if dry_run:
            self.stdout.write('\n=== DRY RUN — no changes will be made ===\n')
        else:
            self.stdout.write('\n=== APPLYING CHANGES ===\n')

        all_tags = list(Tag.objects.annotate(n=Count('taggit_taggeditem_items')))
        tag_by_name = {t.name: t for t in all_tags}
        tag_by_lower = {}
        for t in all_tags:
            key = t.name.lower().strip()
            tag_by_lower.setdefault(key, []).append(t)

        trailing_comma = []   # (dirty_tag, clean_name, clean_tag_or_None)
        case_dupes = []       # list of groups with >1 tag sharing same lower
        encoding_suspects = []

        # --- 1. Trailing comma tags ---
        for tag in all_tags:
            if tag.name.endswith(','):
                clean_name = tag.name.rstrip(',').strip()
                clean_tag = tag_by_name.get(clean_name)
                trailing_comma.append((tag, clean_name, clean_tag))

        # --- 2. Encoding suspects ---
        # Look for tags with replacement characters or common Latin-1 mojibake patterns
        import re
        suspect_pattern = re.compile(r'[^\x00-\x7F\u00C0-\u024F\u1E00-\u1EFF]')
        replacement_char = '\ufffd'
        for tag in all_tags:
            if replacement_char in tag.name or suspect_pattern.search(tag.name):
                encoding_suspects.append(tag)

        # --- 3. Case-insensitive duplicates (excluding trailing-comma ones) ---
        dirty_names = {t.name for t, _, _ in trailing_comma}
        for key, group in tag_by_lower.items():
            if len(group) > 1:
                # Exclude groups that are purely trailing-comma duplicates
                non_dirty = [t for t in group if t.name not in dirty_names]
                if len(non_dirty) > 1:
                    case_dupes.append(group)

        # --- Report: trailing comma ---
        self.stdout.write(f'\n── Trailing comma tags: {len(trailing_comma)} ──')
        total_trailing_items = 0
        for dirty_tag, clean_name, clean_tag in trailing_comma:
            action = 'MERGE into' if clean_tag else 'RENAME to'
            target_uses = clean_tag.n if clean_tag else 0
            total_trailing_items += dirty_tag.n
            self.stdout.write(
                f'  [{dirty_tag.n:3d} uses] "{dirty_tag.name}"  →  {action} "{clean_name}"'
                + (f' [{target_uses} uses]' if clean_tag else ' [new]')
            )

        # --- Report: encoding suspects ---
        self.stdout.write(f'\n── Encoding suspect tags: {len(encoding_suspects)} ──')
        for tag in encoding_suspects[:30]:
            self.stdout.write(f'  [{tag.n:3d} uses] {tag.name!r}')
        if len(encoding_suspects) > 30:
            self.stdout.write(f'  ... and {len(encoding_suspects) - 30} more')

        # --- Report: case duplicates ---
        self.stdout.write(f'\n── Case-insensitive duplicate groups: {len(case_dupes)} ──')
        for group in case_dupes[:20]:
            group_sorted = sorted(group, key=lambda t: -t.n)
            winner = group_sorted[0]
            losers = group_sorted[1:]
            loser_str = ', '.join(f'"{t.name}"[{t.n}]' for t in losers)
            self.stdout.write(f'  KEEP "{winner.name}"[{winner.n}]  ←  merge {loser_str}')
        if len(case_dupes) > 20:
            self.stdout.write(f'  ... and {len(case_dupes) - 20} more groups')

        # --- Summary ---
        rename_count = sum(1 for _, _, ct in trailing_comma if ct is None)
        merge_count = sum(1 for _, _, ct in trailing_comma if ct is not None)
        case_merge_count = sum(len(g) - 1 for g in case_dupes)

        self.stdout.write('\n── Summary ──')
        self.stdout.write(f'  Trailing comma tags to RENAME:       {rename_count}')
        self.stdout.write(f'  Trailing comma tags to MERGE:        {merge_count}')
        self.stdout.write(f'  Tagged items affected (trailing ,):  {total_trailing_items}')
        self.stdout.write(f'  Case-duplicate tags to MERGE:        {case_merge_count}')
        self.stdout.write(f'  Encoding suspects (manual review):   {len(encoding_suspects)}')
        self.stdout.write(f'  Total tags before cleanup:           {len(all_tags)}')
        self.stdout.write(f'  Tags that would be removed:          {merge_count + case_merge_count}')

        if dry_run:
            self.stdout.write('\nRun with --apply to execute.\n')
            return

        # --- Apply ---
        from django.db import transaction

        def merge_tag(source, target):
            """Move all TaggedItems from source to target, skipping duplicates."""
            for item in TaggedItem.objects.filter(tag=source):
                exists = TaggedItem.objects.filter(
                    content_type=item.content_type,
                    object_id=item.object_id,
                    tag=target,
                ).exists()
                if exists:
                    item.delete()
                else:
                    item.tag = target
                    item.save()
            source.delete()

        with transaction.atomic():
            # Trailing comma: merge or rename
            for dirty_tag, clean_name, clean_tag in trailing_comma:
                # Always check for slug collision too, not just name match
                new_slug = Tag(name=clean_name).slugify(clean_name)
                slug_collision = Tag.objects.filter(slug=new_slug).exclude(pk=dirty_tag.pk).first()
                target = clean_tag or slug_collision

                if target:
                    merge_tag(dirty_tag, target)
                    self.stdout.write(f'  Merged "{dirty_tag.name}" → "{target.name}"')
                else:
                    old_name = dirty_tag.name
                    dirty_tag.name = clean_name
                    dirty_tag.slug = new_slug
                    dirty_tag.save()
                    self.stdout.write(f'  Renamed "{old_name}" → "{clean_name}"')

            # Case duplicates: keep most-used, merge rest
            for group in case_dupes:
                group_sorted = sorted(group, key=lambda t: -t.n)
                winner = group_sorted[0]
                for loser in group_sorted[1:]:
                    merge_tag(loser, winner)
                    self.stdout.write(f'  Merged (case) "{loser.name}" → "{winner.name}"')

        self.stdout.write('\nDone.\n')
