import { useState } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Dumbbell, Heart, MessageCircle, Sparkles, Trash2 } from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { timeAgo } from "../lib/format";
import { RecapStats, WorkoutStats } from "./Stats";
import { Avatar, Badge, Button, ErrorBox, Input } from "./ui";

function Comments({ post }) {
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const key = ["comments", post.id];
  const { data: comments = [], isPending } = useQuery({ queryKey: key, queryFn: () => api(`/posts/${post.id}/comments/`) });
  const add = useMutation({
    mutationFn: () => api(`/posts/${post.id}/comments/`, { method: "POST", body: { body } }),
    onSuccess: (comment) => {
      setBody("");
      queryClient.setQueryData(key, (old = []) => [...old, comment]);
    },
  });
  const remove = useMutation({
    mutationFn: (id) => api(`/comments/${id}/`, { method: "DELETE" }),
    onSuccess: (_, id) => queryClient.setQueryData(key, (old = []) => old.filter((c) => c.id !== id)),
  });

  return (
    <div className="space-y-3 border-t border-zinc-100 pt-3 dark:border-zinc-800">
      {isPending ? (
        <p className="text-sm text-zinc-500">Loading comments...</p>
      ) : (
        comments.map((comment) => (
          <div key={comment.id} className="group flex items-start gap-2 text-sm">
            <Avatar src={comment.author.avatar} name={comment.author.username} size={28} />
            <p className="flex-1">
              <Link to={`/u/${comment.author.username}`} className="font-semibold">
                {comment.author.username}
              </Link>{" "}
              {comment.body}
              <span className="ml-2 text-xs text-zinc-400">{timeAgo(comment.created_at)}</span>
            </p>
            {comment.can_delete && (
              <button
                type="button"
                onClick={() => remove.mutate(comment.id)}
                className="text-zinc-400 opacity-0 transition group-hover:opacity-100 hover:text-red-500 focus:opacity-100"
                aria-label="Delete comment"
              >
                <Trash2 className="size-4" />
              </button>
            )}
          </div>
        ))
      )}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (body.trim()) add.mutate();
        }}
      >
        <Input value={body} onChange={(e) => setBody(e.target.value)} placeholder="Add a comment..." maxLength={500} />
        <Button type="submit" variant="secondary" loading={add.isPending} disabled={!body.trim()}>
          Post
        </Button>
      </form>
      <ErrorBox error={add.error} />
    </div>
  );
}

export default function PostCard({ post, onDeleted }) {
  const { user } = useAuth();
  const [liked, setLiked] = useState(post.liked_by_me);
  const [likes, setLikes] = useState(post.like_count);
  const [showComments, setShowComments] = useState(false);

  const like = useMutation({
    mutationFn: (on) => api(`/posts/${post.id}/like/`, { method: on ? "POST" : "DELETE" }),
    onMutate: (on) => {
      setLiked(on); // optimistic: the heart reacts instantly
      setLikes((count) => count + (on ? 1 : -1));
    },
    onSuccess: (data) => setLikes(data.like_count),
    onError: (_, on) => {
      setLiked(!on);
      setLikes((count) => count + (on ? -1 : 1));
    },
  });
  const remove = useMutation({
    mutationFn: () => api(`/posts/${post.id}/`, { method: "DELETE" }),
    onSuccess: () => onDeleted?.(post.id),
  });

  const { width, height, full } = post.photo;
  return (
    <article className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <header className="flex items-center gap-3 px-4 py-3">
        <Avatar src={post.author.avatar} name={post.author.username} size={36} />
        <div className="min-w-0 flex-1">
          <Link to={`/u/${post.author.username}`} className="font-semibold hover:underline">
            {post.author.username}
          </Link>
          <p className="text-xs text-zinc-500">
            <Link to={`/p/${post.id}`} className="hover:underline">
              {timeAgo(post.created_at)}
            </Link>
          </p>
        </div>
        {post.kind === "recap" ? (
          <Badge tone="indigo">
            <Sparkles className="size-3" aria-hidden /> Recap
          </Badge>
        ) : (
          <Badge>
            <Dumbbell className="size-3" aria-hidden /> Workout
          </Badge>
        )}
        {post.is_mine && (
          <button
            type="button"
            onClick={() => window.confirm("Delete this post? The workout stays in your calendar.") && remove.mutate()}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-red-500 dark:hover:bg-zinc-800"
            aria-label="Delete post"
          >
            <Trash2 className="size-4" />
          </button>
        )}
      </header>

      <img
        src={full}
        width={width}
        height={height}
        alt={post.caption || `${post.author.username}'s ${post.kind}`}
        loading="lazy"
        style={{ aspectRatio: `${width} / ${height}` }}
        className="max-h-[680px] w-full bg-zinc-100 object-cover dark:bg-zinc-800"
        onDoubleClick={() => !liked && like.mutate(true)}
      />

      <div className="space-y-3 px-4 py-3">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => like.mutate(!liked)}
            className="flex items-center gap-1.5 text-sm font-medium"
            aria-pressed={liked}
            aria-label={liked ? "Unlike" : "Like"}
          >
            <Heart className={`size-6 transition ${liked ? "fill-red-500 text-red-500" : ""}`} />
            {likes}
          </button>
          <button
            type="button"
            onClick={() => setShowComments((s) => !s)}
            className="flex items-center gap-1.5 text-sm font-medium"
            aria-expanded={showComments}
          >
            <MessageCircle className="size-6" />
            {post.comment_count}
          </button>
          {post.workout_id && (
            <Link to={`/workouts/${post.workout_id}`} className="ml-auto text-sm text-indigo-600 hover:underline dark:text-indigo-400">
              View workout
            </Link>
          )}
        </div>
        {post.caption && (
          <p className="text-sm whitespace-pre-line">
            <span className="font-semibold">{post.author.username}</span> {post.caption}
          </p>
        )}
        {post.kind === "workout" ? (
          <WorkoutStats stats={post.stats} units={user.units} />
        ) : (
          <RecapStats stats={post.stats} units={user.units} />
        )}
        {showComments && <Comments post={post} />}
        <ErrorBox error={remove.error || like.error} />
      </div>
    </article>
  );
}
