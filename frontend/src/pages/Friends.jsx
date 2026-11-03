import { useState } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Users } from "lucide-react";
import { api } from "../api/client";
import { useDebounced } from "../components/ExercisePicker";
import { Avatar, Button, Card, Empty, ErrorBox, Input, PageHeader, Spinner } from "../components/ui";

function PersonRow({ person, children }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <Avatar src={person.avatar} name={person.username} size={40} />
      <Link to={`/u/${person.username}`} className="flex-1 font-medium hover:underline">
        {person.username}
      </Link>
      {children}
    </div>
  );
}

export default function Friends() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const debounced = useDebounced(query.trim(), 300);

  const search = useQuery({
    queryKey: ["users", debounced],
    queryFn: () => api(`/users/?q=${encodeURIComponent(debounced)}`),
    enabled: debounced.length >= 2,
  });
  const requests = useQuery({ queryKey: ["friends", "requests"], queryFn: () => api("/friends/requests/") });
  const friends = useQuery({ queryKey: ["friends", "list"], queryFn: () => api("/friends/") });

  const act = useMutation({
    mutationFn: ({ path, method }) => api(path, { method }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["friends"] });
      queryClient.invalidateQueries({ queryKey: ["posts"] });
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Friends" subtitle="Friends always see each other's posts, even on private accounts." />

      <Card>
        <div className="relative">
          <Search className="pointer-events-none absolute top-3 left-3 size-4 text-zinc-400" aria-hidden />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find people by username" className="pl-9" />
        </div>
        {debounced.length >= 2 && (
          <div className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800">
            {search.isPending ? (
              <Spinner />
            ) : search.data?.length ? (
              search.data.map((person) => (
                <PersonRow key={person.id} person={person}>
                  <Link to={`/u/${person.username}`} className="text-sm text-indigo-600 hover:underline dark:text-indigo-400">
                    View
                  </Link>
                </PersonRow>
              ))
            ) : (
              <p className="py-4 text-center text-sm text-zinc-500">Nobody found.</p>
            )}
          </div>
        )}
      </Card>

      <ErrorBox error={act.error} />

      {requests.data?.incoming.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">Requests</h2>
          <Card className="divide-y divide-zinc-100 py-2 dark:divide-zinc-800">
            {requests.data.incoming.map((request) => (
              <PersonRow key={request.id} person={request.user}>
                <Button size="sm" onClick={() => act.mutate({ path: `/friends/requests/${request.id}/accept/`, method: "POST" })}>
                  Accept
                </Button>
                <Button size="sm" variant="ghost" onClick={() => act.mutate({ path: `/friends/requests/${request.id}/`, method: "DELETE" })}>
                  Decline
                </Button>
              </PersonRow>
            ))}
          </Card>
        </section>
      )}

      {requests.data?.outgoing.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">Sent</h2>
          <Card className="divide-y divide-zinc-100 py-2 dark:divide-zinc-800">
            {requests.data.outgoing.map((request) => (
              <PersonRow key={request.id} person={request.user}>
                <Button size="sm" variant="secondary" onClick={() => act.mutate({ path: `/friends/requests/${request.id}/`, method: "DELETE" })}>
                  Cancel
                </Button>
              </PersonRow>
            ))}
          </Card>
        </section>
      )}

      <section>
        <h2 className="mb-2 font-semibold">Your friends {friends.data ? `(${friends.data.length})` : ""}</h2>
        {friends.isPending ? (
          <Spinner />
        ) : friends.data?.length ? (
          <Card className="divide-y divide-zinc-100 py-2 dark:divide-zinc-800">
            {friends.data.map((friend) => (
              <PersonRow key={friend.id} person={friend} />
            ))}
          </Card>
        ) : (
          <Empty icon={Users} title="No friends yet">
            Search for people above and send a request.
          </Empty>
        )}
      </section>
    </div>
  );
}
