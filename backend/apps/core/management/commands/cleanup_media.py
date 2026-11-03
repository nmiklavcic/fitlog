import shutil
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.images import delete_photo_files
from apps.core.models import Photo


class Command(BaseCommand):
    help = (
        "Delete photos that no post or avatar uses any more, and photo folders on disk "
        "that have no database row (e.g. left by a crash). Run daily from a systemd timer."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report what would be deleted.")
        parser.add_argument("--grace-minutes", type=int, default=60, help="Skip anything newer than this.")

    def handle(self, *args, dry_run=False, grace_minutes=60, **options):
        cutoff = timezone.now() - timedelta(minutes=grace_minutes)

        orphans = Photo.objects.filter(posts__isnull=True, avatar_of__isnull=True, created_at__lt=cutoff)
        orphan_count = 0
        for photo in orphans:
            orphan_count += 1
            if not dry_run:
                delete_photo_files(photo)
                photo.delete()

        # Folders without a row (FileSystemStorage layout: photos/<ab>/<sha256>/).
        known = set(Photo.objects.values_list("sha256", flat=True))
        root = Path(settings.MEDIA_ROOT) / "photos"
        stray_count = 0
        if root.is_dir():
            for folder in root.glob("*/*"):
                if folder.is_dir() and folder.name not in known and folder.stat().st_mtime < time.time() - grace_minutes * 60:
                    stray_count += 1
                    if not dry_run:
                        shutil.rmtree(folder)

        verb = "Would delete" if dry_run else "Deleted"
        self.stdout.write(f"{verb} {orphan_count} unused photo(s) and {stray_count} stray folder(s).")
