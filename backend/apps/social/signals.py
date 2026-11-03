from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.core.images import delete_photo_if_unused

from .models import Post


@receiver(post_delete, sender=Post)
def clean_up_photo(sender, instance, **kwargs):
    """Covers every way a post disappears: deleted directly, with its workout, or with the account."""
    photo_id = instance.photo_id
    transaction.on_commit(lambda: delete_photo_if_unused(photo_id))
