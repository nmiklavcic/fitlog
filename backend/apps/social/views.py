from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import UserSummarySerializer
from apps.core.images import process_upload
from apps.core.metrics import POSTS_CREATED
from apps.workouts.models import Workout
from apps.workouts.services import workout_summary

from . import services
from .models import Comment, Friendship, Like, Notification, Post
from .serializers import (
    CommentSerializer,
    NotificationSerializer,
    PostCreateSerializer,
    PostSerializer,
    PostUpdateSerializer,
    ProfileSerializer,
)
from .visibility import can_view_posts, friend_ids, visible_posts_filter


class FeedPagination(CursorPagination):
    """Cursor pagination stays stable while new posts arrive (no duplicates on 'load more')."""

    page_size = 12
    ordering = "-created_at"


class NotificationPagination(CursorPagination):
    page_size = 20
    ordering = "-created_at"


def annotated_posts(viewer):
    return (
        Post.objects.select_related("author__avatar", "photo")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            liked_by_me=Exists(Like.objects.filter(post=OuterRef("pk"), user=viewer)),
        )
    )


class PostViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PostSerializer
    pagination_class = FeedPagination
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        # Posts the viewer may not see simply don't exist for them (404, not 403).
        return annotated_posts(self.request.user).filter(visible_posts_filter(self.request.user))

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.action == "create":
            self.throttle_scope = "upload"
            throttles.append(ScopedRateThrottle())
        return throttles

    def _page(self, queryset):
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=False)
    def feed(self, request):
        """Your own posts + your friends' posts, newest first."""
        ids = friend_ids(request.user.pk) | {request.user.pk}
        return self._page(annotated_posts(request.user).filter(author_id__in=ids, author__is_active=True))

    @action(detail=False)
    def explore(self, request):
        """Posts from public accounts."""
        return self._page(annotated_posts(request.user).filter(author__is_public=True, author__is_active=True))

    def create(self, request):
        serializer = PostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workout = get_object_or_404(
            Workout.objects.prefetch_related("exercises__exercise", "exercises__sets"),
            pk=serializer.validated_data["workout_id"],
            user=request.user,
        )
        if Post.objects.filter(workout=workout).exists():
            return Response({"detail": "This workout is already shared."}, status=status.HTTP_409_CONFLICT)
        photo = process_upload(serializer.validated_data["photo"])
        try:
            with transaction.atomic():
                post = Post.objects.create(
                    author=request.user,
                    kind=Post.Kind.WORKOUT,
                    workout=workout,
                    stats=workout_summary(workout),
                    photo=photo,
                    caption=serializer.validated_data["caption"].strip(),
                )
        except IntegrityError:  # double submit
            return Response({"detail": "This workout is already shared."}, status=status.HTTP_409_CONFLICT)
        POSTS_CREATED.labels(Post.Kind.WORKOUT).inc()
        return Response(self.get_serializer(self.get_queryset().get(pk=post.pk)).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        post = self.get_object()
        if post.author_id != request.user.pk:
            raise PermissionDenied("Only the author can edit this post.")
        serializer = PostUpdateSerializer(post, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self.get_serializer(self.get_queryset().get(pk=post.pk)).data)

    def destroy(self, request, *args, **kwargs):
        post = self.get_object()
        if post.author_id != request.user.pk:
            raise PermissionDenied("Only the author can delete this post.")
        post.delete()  # the photo is removed by a signal once nothing else uses it
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post", "delete"])
    def like(self, request, pk=None):
        post = self.get_object()
        if request.method == "POST":
            _, created = Like.objects.get_or_create(user=request.user, post=post)
            if created:
                services.notify(post.author, Notification.Kind.LIKE, actor=request.user, post=post)
        else:
            Like.objects.filter(user=request.user, post=post).delete()
        return Response({"liked": request.method == "POST", "like_count": post.likes.count()})

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        post = self.get_object()
        if request.method == "GET":
            comments = post.comments.select_related("author__avatar", "post")[:200]
            return Response(CommentSerializer(comments, many=True, context={"request": request}).data)
        serializer = CommentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(author=request.user, post=post)
        services.notify(post.author, Notification.Kind.COMMENT, actor=request.user, post=post, data={"comment_id": comment.pk})
        return Response(CommentSerializer(comment, context={"request": request}).data, status=status.HTTP_201_CREATED)


class CommentViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    def get_queryset(self):
        # You can delete your own comments, and any comment on your own posts.
        user = self.request.user
        return Comment.objects.filter(Q(author=user) | Q(post__author=user))


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    lookup_field = "username"
    lookup_value_regex = r"[A-Za-z0-9_.]+"
    pagination_class = FeedPagination

    def get_queryset(self):
        return User.objects.filter(is_active=True).select_related("avatar")

    def get_object(self):
        user = self.get_queryset().filter(username__iexact=self.kwargs["username"]).first()
        if user is None:
            raise NotFound("User not found.")
        return user

    def list(self, request):
        """Search people by username: ?q=ali"""
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response([])
        users = self.get_queryset().filter(username__icontains=query).order_by("username")[:20]
        return Response(UserSummarySerializer(users, many=True).data)

    def retrieve(self, request, username=None):
        return Response(ProfileSerializer(self.get_object(), context={"request": request}).data)

    @action(detail=True)
    def posts(self, request, username=None):
        author = self.get_object()
        if not can_view_posts(request.user, author):
            return Response(
                {"detail": "This account is private.", "code": "private_account"}, status=status.HTTP_403_FORBIDDEN
            )
        page = self.paginate_queryset(annotated_posts(request.user).filter(author=author))
        data = PostSerializer(page, many=True, context={"request": request}).data
        return self.get_paginated_response(data)


class FriendListView(APIView):
    def get(self, request):
        friends = User.objects.filter(pk__in=friend_ids(request.user.pk), is_active=True).select_related("avatar")
        return Response(UserSummarySerializer(friends.order_by("username"), many=True).data)


class UnfriendView(APIView):
    def delete(self, request, username):
        other = get_object_or_404(User, username__iexact=username)
        friendship = services.friendship_between(request.user, other)
        if friendship is None or friendship.status != Friendship.Status.ACCEPTED:
            raise NotFound("You're not friends.")
        services.remove_friendship(friendship)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FriendRequestViewSet(viewsets.GenericViewSet):
    def get_queryset(self):
        user = self.request.user
        return Friendship.objects.filter(
            Q(requester=user) | Q(addressee=user), status=Friendship.Status.PENDING
        ).select_related("requester__avatar", "addressee__avatar")

    def list(self, request):
        incoming, outgoing = [], []
        for friendship in self.get_queryset().order_by("-created_at"):
            if friendship.addressee_id == request.user.pk:
                incoming.append({"id": friendship.pk, "user": UserSummarySerializer(friendship.requester).data, "created_at": friendship.created_at})
            else:
                outgoing.append({"id": friendship.pk, "user": UserSummarySerializer(friendship.addressee).data, "created_at": friendship.created_at})
        return Response({"incoming": incoming, "outgoing": outgoing})

    def create(self, request):
        username = str(request.data.get("username", "")).strip()
        recipient = User.objects.filter(username__iexact=username, is_active=True).first()
        if recipient is None:
            raise NotFound("User not found.")
        friendship = services.send_request(request.user, recipient)
        return Response(
            {"id": friendship.pk, "status": friendship.status, "relationship": services.relationship(request.user, recipient)},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        friendship = get_object_or_404(self.get_queryset(), pk=pk)
        services.accept_request(friendship, request.user)
        return Response({"status": "friends"})

    def destroy(self, request, pk=None):
        """Decline an incoming request or cancel an outgoing one."""
        friendship = get_object_or_404(self.get_queryset(), pk=pk)
        services.remove_friendship(friendship)
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related(
            "actor__avatar", "post__photo", "post__author"
        )

    @action(detail=False, url_path="unread-count")
    def unread_count(self, request):
        return Response({"count": services.unread_count(request.user)})

    @action(detail=False, methods=["post"])
    def read(self, request):
        services.mark_all_read(request.user)
        return Response({"count": 0})
