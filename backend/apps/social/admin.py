from django.contrib import admin

from .models import Comment, Friendship, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["id", "author", "kind", "created_at"]
    list_filter = ["kind"]
    search_fields = ["author__username", "caption"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["id", "author", "post", "created_at"]


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ["requester", "addressee", "status", "created_at"]
    list_filter = ["status"]
