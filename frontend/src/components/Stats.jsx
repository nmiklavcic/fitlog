import { Clock, Dumbbell, Flame, Layers, Trophy } from "lucide-react";
import { formatVolume, formatWeight } from "../lib/units";
import { muscleLabel } from "../lib/format";
import { Badge } from "./ui";

function Stat({ icon: Icon, value, label }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Icon className="size-4 text-zinc-400" aria-hidden />
      <span className="font-semibold text-zinc-900 dark:text-zinc-100">{value}</span>
      <span>{label}</span>
    </span>
  );
}

// The stats card on workout posts, shown in the *viewer's* units.
export function WorkoutStats({ stats, units }) {
  if (!stats?.exercises) return null;
  return (
    <div className="rounded-xl bg-zinc-50 p-3 text-sm dark:bg-zinc-800/60">
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-zinc-600 dark:text-zinc-400">
        <Stat icon={Dumbbell} value={stats.exercise_count} label="exercises" />
        <Stat icon={Layers} value={stats.set_count} label="sets" />
        <Stat icon={Flame} value={formatVolume(stats.volume_kg, units)} label="volume" />
        {stats.duration_min ? <Stat icon={Clock} value={stats.duration_min} label="min" /> : null}
        {stats.pr_count > 0 && (
          <Badge tone="amber">
            <Trophy className="size-3" aria-hidden /> {stats.pr_count} PR{stats.pr_count > 1 ? "s" : ""}
          </Badge>
        )}
      </div>
      <ul className="mt-2 divide-y divide-zinc-200 dark:divide-zinc-700">
        {stats.exercises.map((exercise) => (
          <li key={exercise.exercise_id} className="flex items-center justify-between gap-3 py-1.5">
            <span className="flex min-w-0 items-center gap-2">
              <span className="truncate">{exercise.name}</span>
              {exercise.is_pr && <Badge tone="amber">PR</Badge>}
            </span>
            <span className="shrink-0 text-zinc-500">
              {exercise.sets} × {exercise.best_set ? `${formatWeight(exercise.best_set.weight_kg, units)} × ${exercise.best_set.reps}` : "-"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RecapStats({ stats, units }) {
  const tiles = [
    ["Workouts", stats.workouts],
    ["Volume", formatVolume(stats.volume_kg, units)],
    ["PRs", stats.pr_count],
    ["Best streak", `${stats.longest_weekly_streak} wk`],
    ["Most trained", muscleLabel(stats.most_trained_muscle) || "-"],
    ["Top lift", stats.top_exercise || "-"],
  ];
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {tiles.map(([label, value]) => (
        <div key={label} className="rounded-xl bg-zinc-50 p-3 dark:bg-zinc-800/60">
          <p className="text-xs text-zinc-500">{label}</p>
          <p className="truncate font-semibold">{value}</p>
        </div>
      ))}
    </div>
  );
}
