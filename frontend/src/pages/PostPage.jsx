import { useNavigate, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { EyeOff } from "lucide-react";
import { api } from "../api/client";
import PostCard from "../components/PostCard";
import { Empty, ErrorBox, Spinner } from "../components/ui";

export default function PostPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const post = useQuery({ queryKey: ["post", id], queryFn: () => api(`/posts/${id}/`) });

  if (post.isPending) return <Spinner />;
  if (post.error?.status === 404) {
    // Private posts you can't see are indistinguishable from deleted ones (by design).
    return (
      <Empty icon={EyeOff} title="Post not available">
        It was deleted, or it belongs to a private account.
      </Empty>
    );
  }
  if (post.isError) return <ErrorBox error={post.error} />;
  return <PostCard post={post.data} onDeleted={() => navigate("/")} />;
}
