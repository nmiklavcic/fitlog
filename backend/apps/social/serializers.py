from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import UserSummarySerializer
from apps.core.signing import photo_urls

from .models import Comment, Notification, Post
from .services import relationship
from .visibility import can_view_posts, friend_ids


class PostSerializer(serializers.ModelSerializer):
    """A post as shown in feeds. Only ever built for posts the viewer may see."""

    author = UserSummarySerializer(read_only=True)
    photo = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(read_only=True, default=0)
    comment_count = serializers.IntegerField(read_only=True, default=0)
    liked_by_me = serializers.BooleanField(read_only=True, default=False)
    workout_id = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "kind",
            "author",
            "photo",
            "caption",
            "stats",
            "recap_period",
            "workout_id",
            "like_count",
            "comment_count",
            "liked_by_me",
            "is_mine",
            "created_at",
        ]
        read_only_fields = fields

    def _viewer(self):
        return self.context["request"].user

    def get_photo(self, post):
        return photo_urls(post.photo)

    def get_workout_id(self, post):
        # Workouts are private: only the author gets the link to the full workout.
        return post.workout_id if post.author_id == self._viewer().pk else None

    def get_is_mine(self, post):
        return post.author_id == self._viewer().pk


class PostCreateSerializer(serializers.Serializer):
    workout_id = serializers.IntegerField()
    caption = serializers.CharField(max_length=2200, required=False, allow_blank=True, default="")
    photo = serializers.FileField()


class PostUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ["caption"]


class CommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "author", "body", "created_at", "can_delete"]
        read_only_fields = ["id", "author", "created_at", "can_delete"]

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Write something first.")
        return value

    def get_can_delete(self, comment):
        viewer_id = self.context["request"].user.pk
        return viewer_id in (comment.author_id, comment.post.author_id)


class ProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    post_count = serializers.SerializerMethodField()
    friend_count = serializers.SerializerMethodField()
    relationship = serializers.SerializerMethodField()
    can_view_posts = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "bio",
            "avatar",
            "is_public",
            "post_count",
            "friend_count",
            "relationship",
            "can_view_posts",
            "date_joined",
        ]

    def _viewer(self):
        return self.context["request"].user

    def get_avatar(self, user):
        return photo_urls(user.avatar)

    def get_post_count(self, user):
        return user.posts.count()

    def get_friend_count(self, user):
        return len(friend_ids(user.pk))

    def get_relationship(self, user):
        return relationship(self._viewer(), user)

    def get_can_view_posts(self, user):
        return can_view_posts(self._viewer(), user)


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(read_only=True)
    post = serializers.SerializerMethodField()
    read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "kind", "actor", "post", "data", "read", "created_at"]

    def get_post(self, notification):
        post = notification.post
        if post is None or not can_view_posts(self.context["request"].user, post.author):
            return None
        urls = photo_urls(post.photo)
        return {"id": post.id, "thumb": urls["thumb"] if urls else None}

    def get_read(self, notification):
        return notification.read_at is not None
