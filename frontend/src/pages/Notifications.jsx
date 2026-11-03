import { useEffect } from "react";
import { Link } from "react-router";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, CreditCard } from "lucide-react";
import { api, nextPath } from "../api/client";
import { Avatar, Button, Card, Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { timeAgo } from "../lib/format";

function describe(n) {
  switch (n.kind) {
    case "friend_request":
      return { text: "sent you a friend request", to: "/friends" };
    case "friend_accept":
      return { text: "accepted your friend request", to: `/u/${n.actor?.username}` };
    case "like":
      return { text: "liked your post", to: n.post ? `/p/${n.post.id}` : null };
    case "comment":
      return { text: "commented on your post", to: n.post ? `/p/${n.post.id}` : null };
    case "challenge_invite":
      return { text: "challenged you", to: "/leaderboard" };
    case "challenge_accept":
      return { text: "accepted your challenge", to: "/leaderboard" };
    case "challenge_result":
      return {
        text: n.data.draw ? "drew with you in your challenge" : n.data.won ? "lost a challenge to you. You won!" : "won your challenge",
        to: "/leaderboard",
      };
    case "payment_failed":
      return { text: "Your Premium payment failed. Update your card to keep Premium.", to: "/settings" };
    default:
      return { text: n.kind, to: null };
  }
}

export default function Notifications() {
  const queryClient = useQueryClient();
  const list = useInfiniteQuery({
    queryKey: ["notifications", "list"],
    queryFn: ({ pageParam }) => api(pageParam ?? "/notifications/"),
    initialPageParam: null,
    getNextPageParam: (last) => nextPath(last.next),
  });
  const markRead = useMutation({
    mutationFn: () => api("/notifications/read/", { method: "POST" }),
    onSuccess: () => queryClient.setQueryData(["notifications", "unread"], { count: 0 }),
  });
  const { mutate } = markRead;
  const loaded = list.isSuccess;
  useEffect(() => {
    if (loaded) mutate(); // opening the page marks everything as read
  }, [loaded, mutate]);

  const items = list.data?.pages.flatMap((page) => page.results) ?? [];

  return (
    <div>
      <PageHeader title="Notifications" />
      {list.isPending ? (
        <Spinner />
      ) : list.isError ? (
        <ErrorBox error={list.error} />
      ) : items.length === 0 ? (
        <Empty icon={Bell} title="No notifications yet" />
      ) : (
        <Card className="divide-y divide-zinc-100 p-0 dark:divide-zinc-800">
          {items.map((n) => {
            const { text, to } = describe(n);
            const body = (
              <div className={`flex items-center gap-3 px-4 py-3 ${n.read ? "" : "bg-indigo-50/60 dark:bg-indigo-950/30"}`}>
                {n.actor ? (
                  <Avatar src={n.actor.avatar} name={n.actor.username} size={40} />
                ) : (
                  <span className="rounded-full bg-red-100 p-2.5 text-red-600 dark:bg-red-950">
                    <CreditCard className="size-5" aria-hidden />
                  </span>
                )}
                <p className="flex-1 text-sm">
                  {n.actor && <span className="font-semibold">{n.actor.username} </span>}
                  {text}
                  <span className="block text-xs text-zinc-500">{timeAgo(n.created_at)}</span>
                </p>
                {n.post?.thumb && <img src={n.post.thumb} alt="" className="size-11 rounded-lg object-cover" />}
              </div>
            );
            return to ? (
              <Link key={n.id} to={to} className="block hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                {body}
              </Link>
            ) : (
              <div key={n.id}>{body}</div>
            );
          })}
        </Card>
      )}
      {list.hasNextPage && (
        <Button variant="secondary" className="mt-4 w-full" loading={list.isFetchingNextPage} onClick={() => list.fetchNextPage()}>
          Load more
        </Button>
      )}
    </div>
  );
}
