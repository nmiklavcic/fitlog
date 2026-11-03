import { useState } from "react";
import { useNavigate } from "react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { format, subMonths } from "date-fns";
import { Share2, Sparkles } from "lucide-react";
import { api } from "../api/client";
import { RecapStats } from "../components/Stats";
import { Button, Card, ErrorBox, Field, Input, PageHeader, PremiumLock, Select, Spinner } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { formatVolume } from "../lib/units";

export default function Recap() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("month");
  const [month, setMonth] = useState(format(subMonths(new Date(), 0), "yyyy-MM"));
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [caption, setCaption] = useState("");
  const query = mode === "month" ? `month=${month}` : `year=${year}`;

  const recap = useQuery({ queryKey: ["recap", query], queryFn: () => api(`/recap/?${query}`), enabled: user.is_premium });
  const share = useMutation({
    mutationFn: () => api("/recap/share/", { method: "POST", body: { ...(mode === "month" ? { month } : { year }), caption } }),
    onSuccess: (post) => navigate(`/p/${post.id}`),
  });

  if (!user.is_premium) {
    return (
      <div>
        <PageHeader title="Recap" />
        <PremiumLock title="Recaps are a Premium feature">
          Get your month or year in numbers (volume, PRs, streaks, favourite lifts) as a card you can share.
        </PremiumLock>
      </div>
    );
  }

  const r = recap.data;
  return (
    <div className="space-y-4">
      <PageHeader title="Recap" subtitle="Your training, summed up" />
      <Card className="flex flex-wrap items-end gap-3">
        <Field label="Period">
          <Select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="month">Month</option>
            <option value="year">Year</option>
          </Select>
        </Field>
        {mode === "month" ? (
          <Field label="Month">
            <Input type="month" value={month} max={format(new Date(), "yyyy-MM")} onChange={(e) => e.target.value && setMonth(e.target.value)} />
          </Field>
        ) : (
          <Field label="Year">
            <Input type="number" value={year} min="2000" max={new Date().getFullYear()} onChange={(e) => setYear(e.target.value)} className="w-28" />
          </Field>
        )}
      </Card>

      {recap.isPending ? (
        <Spinner />
      ) : recap.isError ? (
        <ErrorBox error={recap.error} />
      ) : (
        <Card className="space-y-4">
          <div className="rounded-2xl bg-linear-to-br from-indigo-600 to-zinc-900 p-5 text-white">
            <p className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-indigo-200 uppercase">
              <Sparkles className="size-3.5" aria-hidden /> Liftlog recap
            </p>
            <p className="mt-1 text-2xl font-bold">{r.label}</p>
            <p className="mt-3 text-sm text-indigo-100">
              {r.workouts} workouts on {r.active_days} days · {r.sets} sets · {r.reps.toLocaleString()} reps ·{" "}
              {formatVolume(r.volume_kg, user.units)}
              {r.volume_change_pct !== null && ` (${r.volume_change_pct > 0 ? "+" : ""}${r.volume_change_pct}% vs. previous period)`}
            </p>
          </div>
          <RecapStats stats={r} units={user.units} />
          <p className="text-sm text-zinc-500">{r.workouts_per_week} workouts per week on average.</p>
          <div className="space-y-2 border-t border-zinc-100 pt-4 dark:border-zinc-800">
            <Field label="Caption (optional)">
              <Input value={caption} onChange={(e) => setCaption(e.target.value)} maxLength={2200} />
            </Field>
            <ErrorBox error={share.error} />
            <Button onClick={() => share.mutate()} loading={share.isPending} disabled={r.workouts === 0}>
              <Share2 className="size-4" /> Share as a post
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
