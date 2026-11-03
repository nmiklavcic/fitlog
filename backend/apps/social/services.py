from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Friendship, Notification
from .visibility import invalidate_friend_ids

UNREAD_TTL = 60


# --- Notifications -------------------------------------------------------------

def _unread_key(user_id):
    return f"notif-unread:{user_id}"


def notify(recipient, kind, actor=None, post=None, data=None):
    if actor is not None and actor.pk == recipient.pk:
        return None  # don't notify people about their own actions
    notification = Notification.objects.create(
        recipient=recipient, actor=actor, kind=kind, post=post, data=data or {}
    )
    cache.delete(_unread_key(recipient.pk))
    return notification


def unread_count(user):
    """Cached for a minute: the frontend polls this every 30 s, so it mostly hits Redis."""
    key = _unread_key(user.pk)
    count = cache.get(key)
    if count is None:
        count = Notification.objects.filter(recipient=user, read_at__isnull=True).count()
        cache.set(key, count, UNREAD_TTL)
    return count


def mark_all_read(user):
    Notification.objects.filter(recipient=user, read_at__isnull=True).update(read_at=timezone.now())
    cache.delete(_unread_key(user.pk))


# --- Friendships -----------------------------------------------------------------

def friendship_between(user_a, user_b):
    return Friendship.objects.filter(
        Q(requester=user_a, addressee=user_b) | Q(requester=user_b, addressee=user_a)
    ).first()


def relationship(viewer, other):
    """How `viewer` relates to `other`, for the profile page's friend button."""
    if viewer.pk == other.pk:
        return {"status": "self", "request_id": None}
    friendship = friendship_between(viewer, other)
    if friendship is None:
        return {"status": "none", "request_id": None}
    if friendship.status == Friendship.Status.ACCEPTED:
        return {"status": "friends", "request_id": None}
    if friendship.requester_id == viewer.pk:
        return {"status": "request_sent", "request_id": friendship.pk}
    return {"status": "request_received", "request_id": friendship.pk}


@transaction.atomic
def send_request(sender, recipient):
    if sender.pk == recipient.pk:
        raise ValidationError({"username": "You can't add yourself."})
    existing = friendship_between(sender, recipient)
    if existing:
        if existing.status == Friendship.Status.ACCEPTED:
            raise ValidationError({"username": "You're already friends."})
        if existing.requester_id == sender.pk:
            raise ValidationError({"username": "Friend request already sent."})
        # They already asked us: sending a request back simply accepts theirs.
        return accept_request(existing, sender)
    try:
        with transaction.atomic():
            friendship = Friendship.objects.create(requester=sender, addressee=recipient)
    except IntegrityError:  # both sides clicked at the same moment
        raise ValidationError({"username": "Friend request already exists."})
    notify(recipient, Notification.Kind.FRIEND_REQUEST, actor=sender)
    return friendship


@transaction.atomic
def accept_request(friendship, user):
    if friendship.addressee_id != user.pk or friendship.status != Friendship.Status.PENDING:
        raise ValidationError({"detail": "This request can't be accepted."})
    friendship.status = Friendship.Status.ACCEPTED
    friendship.responded_at = timezone.now()
    friendship.save(update_fields=["status", "responded_at"])
    invalidate_friend_ids(friendship.requester_id, friendship.addressee_id)
    notify(friendship.requester, Notification.Kind.FRIEND_ACCEPT, actor=user)
    return friendship


def remove_friendship(friendship):
    """Decline, cancel or unfriend: all three just delete the row."""
    friendship.delete()
    invalidate_friend_ids(friendship.requester_id, friendship.addressee_id)
