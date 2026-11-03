from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("posts", views.PostViewSet, basename="post")
router.register("comments", views.CommentViewSet, basename="comment")
router.register("users", views.UserViewSet, basename="user")
router.register("friends/requests", views.FriendRequestViewSet, basename="friend-request")
router.register("notifications", views.NotificationViewSet, basename="notification")

# Router first, so "friends/requests/" never reaches the unfriend route.
urlpatterns = router.urls + [
    path("friends/", views.FriendListView.as_view(), name="friend-list"),
    path("friends/<str:username>/", views.UnfriendView.as_view(), name="unfriend"),
]
