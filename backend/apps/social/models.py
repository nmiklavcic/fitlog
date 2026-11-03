from django.conf import settings
from django.db import models
from django.db.models.functions import Greatest, Least


class Friendship(models.Model):
    """One row per pair of users: a pending request, or (once accepted) a mutual friendship."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"

    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friendships_sent")
    addressee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friendships_received"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # (alice, bob) and (bob, alice) are the same pair: the database enforces one row.
            models.UniqueConstraint(Least("requester", "addressee"), Greatest("requester", "addressee"), name="friendship_pair_unique"),
            models.CheckConstraint(condition=~models.Q(requester=models.F("addressee")), name="friendship_not_self"),
        ]
        indexes = [models.Index(fields=["addressee", "status"], name="friendship_addressee_idx")]


class Post(models.Model):
    class Kind(models.TextChoices):
        WORKOUT = "workout", "Workout"
        RECAP = "recap", "Recap"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.WORKOUT)
    workout = models.OneToOneField(
        "workouts.Workout", null=True, blank=True, on_delete=models.CASCADE, related_name="post"
    )
    recap_period = models.CharField(max_length=7, blank=True)  # "2026-10" or "2026"
    # Snapshot of the stats card, so the feed doesn't recompute PRs for every post.
    stats = models.JSONField(default=dict, blank=True)
    photo = models.ForeignKey("core.Photo", on_delete=models.PROTECT, related_name="posts")
    caption = models.CharField(max_length=2200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["author", "-created_at"], name="post_author_created_idx"),
            models.Index(fields=["-created_at"], name="post_created_idx"),
        ]


class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "post"], name="like_once_per_post")]


class Comment(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    body = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class Notification(models.Model):
    class Kind(models.TextChoices):
        FRIEND_REQUEST = "friend_request", "Friend request"
        FRIEND_ACCEPT = "friend_accept", "Friend request accepted"
        LIKE = "like", "Like"
        COMMENT = "comment", "Comment"
        CHALLENGE_INVITE = "challenge_invite", "Challenge invite"
        CHALLENGE_ACCEPT = "challenge_accept", "Challenge accepted"
        CHALLENGE_RESULT = "challenge_result", "Challenge finished"
        PAYMENT_FAILED = "payment_failed", "Payment failed"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    data = models.JSONField(default=dict, blank=True)  # e.g. {"challenge_id": 3}
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["recipient", "read_at"], name="notification_unread_idx")]
