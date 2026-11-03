from datetime import date

from django.core.management.base import BaseCommand

from apps.insights.models import Challenge
from apps.insights.services import finish_if_over


class Command(BaseCommand):
    help = "Settle challenges whose last day has passed and notify both players (run daily)."

    def handle(self, *args, **options):
        due = Challenge.objects.filter(status=Challenge.Status.ACTIVE, ends_on__lt=date.today()).select_related("creator", "opponent")
        count = 0
        for challenge in due:
            finish_if_over(challenge)
            count += 1
        self.stdout.write(f"Finished {count} challenge(s).")
