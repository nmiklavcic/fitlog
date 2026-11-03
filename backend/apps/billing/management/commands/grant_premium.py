from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.billing.services import grant


class Command(BaseCommand):
    help = "Give a user Premium for N days without payment (for demos and support)."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, username, days, **options):
        user = User.objects.filter(username__iexact=username).first()
        if user is None:
            raise CommandError(f"No user named {username!r}.")
        subscription = grant(user, days)
        self.stdout.write(self.style.SUCCESS(f"{user.username} has Premium until {subscription.current_period_end:%Y-%m-%d %H:%M}."))
