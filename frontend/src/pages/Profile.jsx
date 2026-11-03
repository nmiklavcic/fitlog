import { useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, Globe, Lock, UserCheck, UserPlus } from "lucide-react";
import { api } from "../api/client";
import PostGrid from "../components/PostGrid";
import { Avatar, Badge, Button, ButtonLink, Card, Empty, ErrorBox, Spinner } from "../components/ui";
import { usePostPages } from "./Feed";

function FriendButton({ profile }) {
  const queryClient = useQueryClient();
  const { status, request_id: requestId } = profile.relationship;
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["profile", profile.username] });
    queryClient.invalidateQueries({ queryKey: ["friends"] });
    queryClient.invalidateQueries({ queryKey: ["posts"] });
  };
  const action = useMutation({
    mutationFn: ({ path, method, body }) => api(path, { method, body }),
    onSuccess: refresh,
  });
  const run = (path, method = "POST") => action.mutate({ path, method });

  let content;
  if (status === "self") {
    content = (
      <ButtonLink to="/settings" variant="secondary" size="sm">
        Edit profile
      </ButtonLink>
    );
  } else if (status === "none") {
    content = (
      <Button size="sm" loading={action.isPending} onClick={() => action.mutate({ path: "/friends/requests/", method: "POST", body: { username: profile.username } })}>
        <UserPlus className="size-4" /> Add friend
      </Button>
    );
  } else if (status === "request_sent") {
    content = (
      <Button variant="secondary" size="sm" loading={action.isPending} onClick={() => run(`/friends/requests/${requestId}/`, "DELETE")}>
        Requested · Cancel
      </Button>
    );
  } else if (status === "request_received") {
    content = (
      <div className="flex gap-2">
        <Button size="sm" loading={action.isPending} onClick={() => run(`/friends/requests/${requestId}/accept/`)}>
          Accept request
        </Button>
        <Button variant="secondary" size="sm" onClick={() => run(`/friends/requests/${requestId}/`, "DELETE")}>
          Decline
        </Button>
      </div>
    );
  } else {
    content = (
      <Button
        variant="secondary"
        size="sm"
        loading={action.isPending}
        onClick={() => window.confirm(`Remove ${profile.username} from your friends?`) && run(`/friends/${profile.username}/`, "DELETE")}
      >
        <UserCheck className="size-4" /> Friends
      </Button>
    );
  }
  return (
    <div className="space-y-2">
      {content}
      <ErrorBox error={action.error} />
    </div>
  );
}

export default function Profile() {
  const { username } = useParams();
  const profile = useQuery({ queryKey: ["profile", username], queryFn: () => api(`/users/${username}/`) });
  const canView = profile.data?.can_view_posts;
  const posts = usePostPages(["posts", "user", username], `/users/${username}/posts/`, { enabled: Boolean(canView) });
  const list = posts.data?.pages.flatMap((page) => page.results) ?? [];

  if (profile.isPending) return <Spinner />;
  if (profile.isError) return <ErrorBox error={profile.error} />;
  const p = profile.data;

  return (
    <div className="space-y-6">
      <Card className="flex flex-col items-center gap-4 text-center sm:flex-row sm:items-start sm:text-left">
        <Avatar src={p.avatar?.full} name={p.username} size={96} />
        <div className="flex-1 space-y-2">
          <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
            <h1 className="text-xl font-bold">{p.username}</h1>
            {p.is_public ? (
              <Badge>
                <Globe className="size-3" aria-hidden /> Public
              </Badge>
            ) : (
              <Badge>
                <Lock className="size-3" aria-hidden /> Private
              </Badge>
            )}
          </div>
          <div className="flex justify-center gap-5 text-sm sm:justify-start">
            <span>
              <b>{p.post_count}</b> posts
            </span>
            <span>
              <b>{p.friend_count}</b> friends
            </span>
          </div>
          {p.bio && <p className="text-sm whitespace-pre-line">{p.bio}</p>}
          <FriendButton profile={p} />
        </div>
      </Card>

      {!canView ? (
        <Empty icon={Lock} title="This account is private">
          Become friends with {p.username} to see their workouts.
        </Empty>
      ) : posts.isPending ? (
        <Spinner />
      ) : list.length === 0 ? (
        <Empty icon={Camera} title="No posts yet" />
      ) : (
        <div className="space-y-4">
          <PostGrid posts={list} />
          {posts.hasNextPage && (
            <Button variant="secondary" className="w-full" loading={posts.isFetchingNextPage} onClick={() => posts.fetchNextPage()}>
              Load more
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
