import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, Compass, Users } from "lucide-react";
import { api, nextPath } from "../api/client";
import PostCard from "../components/PostCard";
import { Button, ButtonLink, Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";

// Shared by the feed and a user's profile: cursor-paginated posts.
export function usePostPages(key, firstPath, options = {}) {
  return useInfiniteQuery({
    queryKey: key,
    queryFn: ({ pageParam }) => api(pageParam ?? firstPath),
    initialPageParam: null,
    getNextPageParam: (lastPage) => nextPath(lastPage.next),
    ...options,
  });
}

export function removePostFromPages(queryClient, key, postId) {
  queryClient.setQueryData(key, (data) =>
    data && { ...data, pages: data.pages.map((page) => ({ ...page, results: page.results.filter((p) => p.id !== postId) })) }
  );
}

export default function Feed() {
  const queryClient = useQueryClient();
  const key = ["posts", "feed"];
  const feed = usePostPages(key, "/posts/feed/");
  const posts = feed.data?.pages.flatMap((page) => page.results) ?? [];

  return (
    <div>
      <PageHeader
        title="Feed"
        subtitle="You and your friends"
        action={
          <ButtonLink to="/log" size="sm">
            Log workout
          </ButtonLink>
        }
      />
      {feed.isPending ? (
        <Spinner />
      ) : feed.isError ? (
        <ErrorBox error={feed.error} />
      ) : posts.length === 0 ? (
        <Empty icon={Camera} title="Your feed is empty">
          <p>Finish a workout and share it, or add friends to see their progress.</p>
          <div className="mt-4 flex justify-center gap-2">
            <ButtonLink to="/friends" variant="secondary" size="sm">
              <Users className="size-4" /> Find friends
            </ButtonLink>
            <ButtonLink to="/explore" variant="secondary" size="sm">
              <Compass className="size-4" /> Explore
            </ButtonLink>
          </div>
        </Empty>
      ) : (
        <div className="space-y-6">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} onDeleted={(id) => removePostFromPages(queryClient, key, id)} />
          ))}
          {feed.hasNextPage && (
            <Button variant="secondary" className="w-full" loading={feed.isFetchingNextPage} onClick={() => feed.fetchNextPage()}>
              Load more
            </Button>
          )}
          {!feed.hasNextPage && <p className="py-4 text-center text-sm text-zinc-500">You're all caught up.</p>}
        </div>
      )}
    </div>
  );
}
