import { Link } from "react-router";
import { Heart, MessageCircle, Sparkles } from "lucide-react";

// Instagram-style 3-column grid of square thumbnails.
export default function PostGrid({ posts }) {
  return (
    <div className="grid grid-cols-3 gap-1 sm:gap-2">
      {posts.map((post) => (
        <Link
          key={post.id}
          to={`/p/${post.id}`}
          className="group relative aspect-square overflow-hidden rounded-md bg-zinc-200 sm:rounded-xl dark:bg-zinc-800"
        >
          <img src={post.photo.thumb} alt="" loading="lazy" className="size-full object-cover transition group-hover:scale-105" />
          {post.kind === "recap" && (
            <Sparkles className="absolute top-2 right-2 size-4 text-white drop-shadow" aria-label="Recap" />
          )}
          <span className="absolute inset-0 hidden items-center justify-center gap-4 bg-black/40 text-sm font-semibold text-white group-hover:flex">
            <span className="flex items-center gap-1">
              <Heart className="size-4 fill-white" aria-hidden /> {post.like_count}
            </span>
            <span className="flex items-center gap-1">
              <MessageCircle className="size-4 fill-white" aria-hidden /> {post.comment_count}
            </span>
          </span>
        </Link>
      ))}
    </div>
  );
}
