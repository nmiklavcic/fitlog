import { useState } from "react";
import { useSearchParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, ComposedChart, Bar, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { ChartLine, Lock, Search } from "lucide-react";
import { api } from "../api/client";
import ExercisePicker from "../components/ExercisePicker";
import { Button, ButtonLink, Card, Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { kgToDisplay, trimNumber } from "../lib/units";

const RANGES = [
  { value: "90", label: "90 days", premium: false },
  { value: "365", label: "1 year", premium: true },
  { value: "all", label: "All time", premium: true },
];

function useRecentExercises() {
  return useQuery({
    queryKey: ["workouts", "recent"],
    queryFn: () => api("/workouts/"),
    select: (workouts) => {
      const seen = new Map();
      workouts.forEach((w) => w.exercises.forEach((we) => seen.set(we.exercise.id, we.exercise)));
      return [...seen.values()].slice(0, 8);
    },
  });
}

export default function Progress() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [pickerOpen, setPickerOpen] = useState(false);
  const exerciseId = params.get("exercise");
  const range = params.get("range") || "90";
  const recent = useRecentExercises();

  const progress = useQuery({
    queryKey: ["progress", exerciseId, range],
    queryFn: () => api(`/exercises/${exerciseId}/progress/?range=${range}`),
    enabled: Boolean(exerciseId),
  });
  const select = (id, nextRange = range) => setParams({ exercise: String(id), range: nextRange });

  const units = user.units;
  const points = (progress.data?.points ?? []).map((p) => ({
    date: p.date.slice(5),
    e1rm: Number(trimNumber(kgToDisplay(p.best_e1rm_kg, units))),
    max: Number(trimNumber(kgToDisplay(p.max_weight_kg, units))),
    volume: Math.round(kgToDisplay(p.volume_kg, units)),
  }));
  const best = points.reduce((acc, p) => ({ e1rm: Math.max(acc.e1rm, p.e1rm), max: Math.max(acc.max, p.max) }), { e1rm: 0, max: 0 });

  return (
    <div>
      <PageHeader title="Progress" subtitle="Strength over time, per exercise" />
      <div className="mb-4 flex flex-wrap gap-2">
        {recent.data?.map((exercise) => (
          <Button
            key={exercise.id}
            size="sm"
            variant={String(exercise.id) === exerciseId ? "primary" : "secondary"}
            onClick={() => select(exercise.id)}
          >
            {exercise.name}
          </Button>
        ))}
        <Button size="sm" variant="ghost" onClick={() => setPickerOpen(true)}>
          <Search className="size-4" /> Other exercise
        </Button>
      </div>

      {!exerciseId ? (
        <Empty icon={ChartLine} title="Pick an exercise">
          Your heaviest set, estimated 1-rep max and volume for every session.
        </Empty>
      ) : (
        <Card>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">{progress.data?.exercise.name ?? "..."}</h2>
            <div className="flex gap-1">
              {RANGES.map((option) => {
                const locked = option.premium && !user.is_premium;
                return (
                  <Button
                    key={option.value}
                    size="sm"
                    variant={range === option.value ? "primary" : "ghost"}
                    onClick={() => !locked && select(exerciseId, option.value)}
                    title={locked ? "Premium feature" : undefined}
                    className={locked ? "opacity-60" : ""}
                  >
                    {locked && <Lock className="size-3" aria-label="Premium" />}
                    {option.label}
                  </Button>
                );
              })}
            </div>
          </div>
          {progress.isPending ? (
            <Spinner />
          ) : progress.error?.status === 402 ? (
            <div className="py-8 text-center">
              <p className="mb-3 text-sm text-zinc-500">Long-term history is a Premium feature.</p>
              <ButtonLink to="/premium" variant="premium" size="sm">
                Upgrade
              </ButtonLink>
            </div>
          ) : progress.isError ? (
            <ErrorBox error={progress.error} />
          ) : points.length === 0 ? (
            <p className="py-8 text-center text-sm text-zinc-500">No sessions in this range.</p>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-xl bg-zinc-50 p-2 dark:bg-zinc-800/60">
                  <p className="text-xs text-zinc-500">Sessions</p>
                  <p className="font-semibold">{points.length}</p>
                </div>
                <div className="rounded-xl bg-zinc-50 p-2 dark:bg-zinc-800/60">
                  <p className="text-xs text-zinc-500">Heaviest</p>
                  <p className="font-semibold">
                    {best.max} {units}
                  </p>
                </div>
                <div className="rounded-xl bg-zinc-50 p-2 dark:bg-zinc-800/60">
                  <p className="text-xs text-zinc-500">Best e1RM</p>
                  <p className="font-semibold">
                    {best.e1rm} {units}
                  </p>
                </div>
              </div>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={points} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="currentColor" strokeOpacity={0.1} />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis yAxisId="weight" tick={{ fontSize: 12 }} />
                    <YAxis yAxisId="volume" orientation="right" tick={{ fontSize: 12 }} hide />
                    <Tooltip contentStyle={{ borderRadius: 12 }} />
                    <Legend />
                    <Bar yAxisId="volume" dataKey="volume" name={`Volume (${units})`} fill="#c7d2fe" radius={[4, 4, 0, 0]} />
                    <Line yAxisId="weight" dataKey="e1rm" name={`Est. 1RM (${units})`} stroke="#4f46e5" strokeWidth={2.5} dot={{ r: 3 }} />
                    <Line yAxisId="weight" dataKey="max" name={`Heaviest (${units})`} stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-xs text-zinc-500">
                Estimated 1RM uses the Epley formula: weight × (1 + reps / 30).
              </p>
            </>
          )}
        </Card>
      )}
      <ExercisePicker open={pickerOpen} onClose={() => setPickerOpen(false)} onSelect={(exercise) => select(exercise.id)} />
    </div>
  );
}
