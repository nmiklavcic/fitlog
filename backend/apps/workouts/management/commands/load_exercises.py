import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.workouts.models import Exercise

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "exercises.json"
FIELDS = ["name", "category", "equipment", "level", "primary_muscles", "secondary_muscles", "instructions"]


class Command(BaseCommand):
    help = "Load (or refresh) the shared exercise catalogue from data/exercises.json. Safe to re-run."

    @transaction.atomic
    def handle(self, *args, **options):
        rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        existing = {e.slug: e for e in Exercise.objects.filter(owner__isnull=True)}
        to_create, to_update = [], []
        for row in rows:
            exercise = existing.get(row["slug"])
            if exercise is None:
                to_create.append(Exercise(slug=row["slug"], **{f: row[f] for f in FIELDS}))
                continue
            if any(getattr(exercise, f) != row[f] for f in FIELDS):
                for f in FIELDS:
                    setattr(exercise, f, row[f])
                to_update.append(exercise)
        Exercise.objects.bulk_create(to_create, batch_size=500)
        Exercise.objects.bulk_update(to_update, FIELDS, batch_size=500)
        self.stdout.write(
            self.style.SUCCESS(
                f"Exercises: {len(to_create)} created, {len(to_update)} updated, {len(rows)} in catalogue."
            )
        )
