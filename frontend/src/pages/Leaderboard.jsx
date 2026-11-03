import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addDays, format, parseISO, startOfWeek } from "date-fns";
import { ChevronLeft, ChevronRight, Medal, Swords, Trophy } from "lucide-react";
import { api, fieldErrors } from "../api/client";
import ExercisePicker from "../components/ExercisePicker";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, PremiumLock, Select, Spinner } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { niceDate, todayIso } from "../lib/format";
import { formatVolume } from "../lib/units";

const METRICS = [
  { key: "volume_kg", label: "Volume" },
  { key: "workouts", label: "Workouts" },
  { key: "prs", label: "PRs" },
];
const CHALLENGE_METRICS = {
  total_volume: "Total volume",
  workout_count: "Number of workouts",
  exercise_volume: "Volume on one exercise",
};

function WeeklyBoard({ units }) {
  const [week, setWeek] = useState(() => startOfWeek(new Date(), { weekStartsOn: 1 }));
  const [metric, setMetric] = useState("volume_kg");
  const iso = format(week, "yyyy-MM-dd");
  const board = useQuery({ queryKey: ["leaderboard", iso], queryFn: () => api(`/leaderboards/weekly/?week=${iso}`) });
  const rows = [...(board.data?.rows ?? [])].sort((a, b) => b[metric] - a[metric]);
  const show = (row) => (metric === "volume_kg" ? formatVolume(row.volume_kg, units) : row[metric]);

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between gap-2">
        <Button size="icon" variant="ghost" onClick={() => setWeek((w) => addDays(w, -7))} aria-label="Previous week">
          <ChevronLeft className="size-4" />
        </Button>
        <h2 className="text-center font-semibold">
          Week of {format(week, "d MMM")} – {format(addDays(week, 6), "d MMM")}
        </h2>
        <Button size="icon" variant="ghost" onClick={() => setWeek((w) => addDays(w, 7))} aria-label="Next week">
          <ChevronRight className="size-4" />
        </Button>
      </div>
      <div className="mb-3 flex justify-center gap-1">
        {METRICS.map((m) => (
          <Button key={m.key} size="sm" variant={metric === m.key ? "primary" : "ghost"} onClick={() => setMetric(m.key)}>
            {m.label}
          </Button>
        ))}
      </div>
      {board.isPending ? (
        <Spinner />
      ) : board.isError ? (
        <ErrorBox error={board.error} />
      ) : (
        <ol className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {rows.map((row, i) => (
            <li key={row.user_id} className={`flex items-center gap-3 px-2 py-2.5 ${row.is_me ? "rounded-xl bg-indigo-50 dark:bg-indigo-950/40" : ""}`}>
              <span className="w-6 text-center font-bold text-zinc-400">
                {i < 3 && row[metric] > 0 ? <Medal className={`size-5 ${["text-amber-400", "text-zinc-400", "text-orange-400"][i]}`} aria-label={`#${i + 1}`} /> : i + 1}
              </span>
              <span className="flex-1 font-medium">
                {row.username} {row.is_me && <span className="text-xs text-zinc-500">(you)</span>}
              </span>
              <span className="font-semibold tabular-nums">{show(row)}</span>
            </li>
          ))}
        </ol>
      )}
      {rows.length === 1 && <p className="mt-3 text-center text-sm text-zinc-500">Add friends to compete with them here.</p>}
    </Card>
  );
}

function NewChallenge({ open, onClose }) {
  const queryClient = useQueryClient();
  const friends = useQuery({ queryKey: ["friends", "list"], queryFn: () => api("/friends/"), enabled: open });
  const [form, setForm] = useState({ opponent_username: "", metric: "total_volume", starts_on: todayIso(), ends_on: format(addDays(new Date(), 6), "yyyy-MM-dd") });
  const [exercise, setExercise] = useState(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const create = useMutation({
    mutationFn: () => api("/challenges/", { method: "POST", body: { ...form, exercise_id: exercise?.id ?? null } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["challenges"] });
      onClose();
    },
  });
  const errors = fieldErrors(create.error);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  return (
    <Modal open={open} onClose={onClose} title="New challenge">
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Field label="Friend" error={errors.opponent_username}>
          <Select value={form.opponent_username} onChange={set("opponent_username")} required>
            <option value="">Choose a friend</option>
            {friends.data?.map((f) => (
              <option key={f.id} value={f.username}>
                {f.username}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Goal">
          <Select value={form.metric} onChange={set("metric")}>
            {Object.entries(CHALLENGE_METRICS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        {form.metric === "exercise_volume" && (
          <Field label="Exercise" error={errors.exercise_id}>
            <Button variant="secondary" className="w-full justify-start" onClick={() => setPickerOpen(true)}>
              {exercise ? exercise.name : "Pick an exercise"}
            </Button>
          </Field>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Starts" error={errors.starts_on}>
            <Input type="date" min={todayIso()} value={form.starts_on} onChange={set("starts_on")} required />
          </Field>
          <Field label="Ends" error={errors.ends_on}>
            <Input type="date" min={form.starts_on} value={form.ends_on} onChange={set("ends_on")} required />
          </Field>
        </div>
        {!Object.keys(errors).length && <ErrorBox error={create.error} />}
        <Button type="submit" className="w-full" loading={create.isPending}>
          Send challenge
        </Button>
      </form>
      <ExercisePicker open={pickerOpen} onClose={() => setPickerOpen(false)} onSelect={setExercise} />
    </Modal>
  );
}

function ChallengeCard({ challenge, me, units }) {
  const queryClient = useQueryClient();
  const respond = useMutation({
    mutationFn: (accept) => api(`/challenges/${challenge.id}/${accept ? "accept" : "decline"}/`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["challenges"] }),
  });
  const iAmCreator = challenge.creator.id === me.id;
  const other = iAmCreator ? challenge.opponent : challenge.creator;
  const scores = challenge.scores;
  const mine = scores ? (iAmCreator ? scores.creator : scores.opponent) : 0;
  const theirs = scores ? (iAmCreator ? scores.opponent : scores.creator) : 0;
  const fmt = (v) => (challenge.metric === "workout_count" ? v : formatVolume(v, units));
  const total = mine + theirs || 1;

  return (
    <Card className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold">You vs. {other.username}</p>
          <p className="text-sm text-zinc-500">
            {CHALLENGE_METRICS[challenge.metric]}
            {challenge.exercise && `: ${challenge.exercise.name}`} · {niceDate(challenge.starts_on, "d MMM")} – {niceDate(challenge.ends_on, "d MMM")}
          </p>
        </div>
        <Badge tone={challenge.status === "active" ? "green" : challenge.status === "pending" ? "amber" : "zinc"}>{challenge.status}</Badge>
      </div>
      {scores && (
        <div>
          <div className="mb-1 flex justify-between text-sm font-medium">
            <span>You: {fmt(mine)}</span>
            <span>
              {other.username}: {fmt(theirs)}
            </span>
          </div>
          <div className="flex h-2.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
            <div className="bg-indigo-600" style={{ width: `${(mine / total) * 100}%` }} />
            <div className="bg-amber-400" style={{ width: `${(theirs / total) * 100}%` }} />
          </div>
        </div>
      )}
      {challenge.status === "finished" && (
        <p className="flex items-center gap-1.5 text-sm font-medium">
          <Trophy className="size-4 text-amber-500" aria-hidden />
          {challenge.winner_id === null ? "It's a draw!" : challenge.winner_id === me.id ? "You won!" : `${other.username} won.`}
        </p>
      )}
      {challenge.status === "pending" && !iAmCreator && (
        <div className="flex gap-2">
          <Button size="sm" loading={respond.isPending} onClick={() => respond.mutate(true)}>
            Accept
          </Button>
          <Button size="sm" variant="ghost" onClick={() => respond.mutate(false)}>
            Decline
          </Button>
        </div>
      )}
      {challenge.status === "pending" && iAmCreator && <p className="text-sm text-zinc-500">Waiting for {other.username} to accept.</p>}
      <ErrorBox error={respond.error} />
    </Card>
  );
}

export default function Leaderboard() {
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);
  // Anyone can see and accept challenges they were invited to; creating one needs Premium.
  const challenges = useQuery({ queryKey: ["challenges"], queryFn: () => api("/challenges/") });

  return (
    <div className="space-y-6">
      <PageHeader title="Leaderboard" subtitle="Friendly competition with your friends" />
      {user.is_premium ? (
        <WeeklyBoard units={user.units} />
      ) : (
        <PremiumLock title="Leaderboards are a Premium feature">
          Rank yourself against your friends every week by volume, workouts and PRs.
        </PremiumLock>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 font-semibold">
            <Swords className="size-5" aria-hidden /> Challenges
          </h2>
          {user.is_premium && (
            <Button size="sm" onClick={() => setCreating(true)}>
              New challenge
            </Button>
          )}
        </div>
        {challenges.isPending ? (
          <Spinner />
        ) : challenges.isError ? (
          <ErrorBox error={challenges.error} />
        ) : challenges.data.length === 0 ? (
          <Empty icon={Swords} title="No challenges yet">
            {user.is_premium ? "Challenge a friend to see who trains harder." : "When a friend challenges you, it shows up here."}
          </Empty>
        ) : (
          <div className="space-y-3">
            {challenges.data.map((challenge) => (
              <ChallengeCard key={challenge.id} challenge={challenge} me={user} units={user.units} />
            ))}
          </div>
        )}
      </section>
      <NewChallenge open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}
