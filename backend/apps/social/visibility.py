"""The single source of truth for "who may see whose posts".

Rule: you can see a user's posts if it's you, if you're friends, or if their
account is public. Feed/explore/profile querysets, post detail, likes,
comments and photo-URL signing all go through these helpers.
Workouts, the calendar and progress are never shared (owner-only querysets).
"""
from django.core.cache import cache
from django.db.models import Q

FRIEND_IDS_TTL = 10 * 60


def _friend_ids_key(user_id):
    return f"friend-ids:{user_id}"


def friend_ids(user_id):
    """IDs of accepted friends, cached in Redis (invalidated on every friendship change)."""
    from .models import Friendship

    key = _friend_ids_key(user_id)
    ids = cache.get(key)
    if ids is None:
        rows = Friendship.objects.filter(
            Q(requester_id=user_id) | Q(addressee_id=user_id), status=Friendship.Status.ACCEPTED
        ).values_list("requester_id", "addressee_id")
        ids = sorted({a if b == user_id else b for a, b in rows})
        cache.set(key, ids, FRIEND_IDS_TTL)
    return set(ids)


def invalidate_friend_ids(*user_ids):
    cache.delete_many([_friend_ids_key(uid) for uid in user_ids])


def are_friends(user_a_id, user_b_id):
    return user_b_id in friend_ids(user_a_id)


def can_view_posts(viewer, author):
    if not author.is_active:
        return False
    if viewer.pk == author.pk or author.is_public:
        return True
    return are_friends(viewer.pk, author.pk)


def visible_posts_filter(viewer):
    """Q filter on Post for everything `viewer` may see."""
    return Q(author__is_active=True) & (
        Q(author_id=viewer.pk) | Q(author__is_public=True) | Q(author_id__in=friend_ids(viewer.pk))
    )
