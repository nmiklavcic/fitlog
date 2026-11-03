from django.core.management.base import BaseCommand, CommandError

from apps.billing import services


class Command(BaseCommand):
    help = "Create the Liftlog Premium product and its monthly/yearly prices in Stripe (safe to re-run)."

    def handle(self, *args, **options):
        if not services.stripe_enabled():
            raise CommandError("STRIPE_SECRET_KEY is not set (demo billing mode needs no setup).")
        client = services.client()
        lookup_keys = [plan["lookup_key"] for plan in services.PLANS.values()]
        existing = {p.lookup_key for p in client.v1.prices.list(params={"lookup_keys": lookup_keys, "active": True}).data}

        product_id = None
        for name, plan in services.PLANS.items():
            if plan["lookup_key"] in existing:
                self.stdout.write(f"{name}: price already exists ({plan['lookup_key']})")
                continue
            if product_id is None:
                product_id = client.v1.products.create(
                    params={"name": services.PRODUCT_NAME, "description": "Advanced analytics, body metrics, recaps, leaderboards and challenges."}
                ).id
            price = client.v1.prices.create(
                params={
                    "product": product_id,
                    "currency": services.CURRENCY,
                    "unit_amount": plan["amount"],
                    "recurring": {"interval": plan["interval"]},
                    "lookup_key": plan["lookup_key"],
                }
            )
            self.stdout.write(self.style.SUCCESS(f"{name}: created {price.id} ({plan['lookup_key']})"))
