import { Compass } from "lucide-react";
import PostGrid from "../components/PostGrid";
import { Button, Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { usePostPages } from "./Feed";

export default function Explore() {
  const explore = usePostPages(["posts", "explore"], "/posts/explore/");
  const posts = explore.data?.pages.flatMap((page) => page.results) ?? [];

  return (
    <div>
      <PageHeader title="Explore" subtitle="Workouts from public accounts" />
      {explore.isPending ? (
        <Spinner />
      ) : explore.isError ? (
        <ErrorBox error={explore.error} />
      ) : posts.length === 0 ? (
        <Empty icon={Compass} title="Nothing here yet">
          Public accounts' posts show up here.
        </Empty>
      ) : (
        <div className="space-y-4">
          <PostGrid posts={posts} />
          {explore.hasNextPage && (
            <Button
              variant="secondary"
              className="w-full"
              loading={explore.isFetchingNextPage}
              onClick={() => explore.fetchNextPage()}
            >
              Load more
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
