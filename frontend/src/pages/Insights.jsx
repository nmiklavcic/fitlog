import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { addDays, format, getDay, parseISO, startOfWeek } from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "../api/client";
import { Button, Card, ErrorBox, PageHeader, PremiumLock, Spinner } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { muscleLabel } from "../lib/format";
import { kgToDisplay } from "../lib/units";

const COLORS = ["#4f46e5", "#f59e0b", "#10b981", "#ef4444", "#06b6d4", "#a855f7", "#84cc16", "#64748b"];

function MuscleVolume({ units }) {
  const [metric, setMetric] = useState("sets");
  const data = useQuery({ queryKey: ["insights", "muscles"], queryFn: () => api("/analytics/muscle-volume/?weeks=12") });
  if (data.isPending) return <Spinner />;
  if (data.isError) return <ErrorBox error={data.error} />;

  const series = metric === "sets" ? data.data.sets : data.data.volume_kg;
  const totals = Object.entries(series).map(([muscle, values]) => [muscle, values.reduce((a, b) => a + b, 0)]);
  const top = totals.sort((a, b) => b[1] - a[1]).slice(0, 7).map(([m]) => m);
  const rows = data.data.weeks.map((week, i) => {
    const row = { week: format(parseISO(week), "d MMM") };
    top.forEach((muscle) => {
      const value = series[muscle][i];
      row[muscle] = metric === "sets" ? value : Math.round(kgToDisplay(value, units));
    });
    return row;
  });

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">Weekly {metric === "sets" ? "sets" : "volume"} per muscle</h2>
        <div className="flex gap-1">
          {["sets", "volume"].map((m) => (
            <Button key={m} size="sm" variant={metric === m ? "primary" : "ghost"} onClick={() => setMetric(m)}>
              {m === "sets" ? "Sets" : `Volume (${units})`}
            </Button>
          ))}
        </div>
      </div>
      {top.length === 0 ? (
        <p className="py-8 text-center text-sm text-zinc-500">Log some workouts to see this chart.</p>
      ) : (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" strokeOpacity={0.1} />
              <XAxis dataKey="week" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ borderRadius: 12 }} />
              <Legend formatter={muscleLabel} />
              {top.map((muscle, i) => (
                <Bar key={muscle} dataKey={muscle} name={muscle} stackId="a" fill={COLORS[i % COLORS.length]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

function Heatmap({ units }) {
  const [year, setYear] = useState(new Date().getFullYear());
  const data = useQuery({ queryKey: ["insights", "heatmap", year], queryFn: () => api(`/analytics/heatmap/?year=${year}`) });
  const days = data.data?.days ?? {};
  const volumes = Object.values(days).map((d) => d.volume_kg || 0).sort((a, b) => a - b);
  const quantile = (q) => volumes[Math.floor(q * (volumes.length - 1))] ?? 0;
  const thresholds = [quantile(0.25), quantile(0.5), quantile(0.75)];
  const level = (volume) => (volume === undefined ? 0 : 1 + thresholds.filter((t) => volume > t).length);
  const shades = ["bg-zinc-100 dark:bg-zinc-800", "bg-indigo-200", "bg-indigo-400", "bg-indigo-600", "bg-indigo-800"];

  const first = startOfWeek(new Date(year, 0, 1), { weekStartsOn: 1 });
  const weeks = Array.from({ length: 53 }, (_, w) =>
    Array.from({ length: 7 }, (_, d) => {
      const date = addDays(first, w * 7 + d);
      return date.getFullYear() === year ? date : null;
    })
  );
  const total = Object.values(days).reduce((sum, d) => sum + d.workouts, 0);

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">
          {total} workouts in {year}
        </h2>
        <div className="flex items-center gap-1">
          <Button size="icon" variant="ghost" onClick={() => setYear((y) => y - 1)} aria-label="Previous year">
            <ChevronLeft className="size-4" />
          </Button>
          <span className="text-sm font-medium tabular-nums">{year}</span>
          <Button size="icon" variant="ghost" onClick={() => setYear((y) => y + 1)} aria-label="Next year">
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>
      {data.isPending ? (
        <Spinner />
      ) : (
        <div className="overflow-x-auto pb-1">
          <div className="flex gap-[3px]">
            {weeks.map((week, w) => (
              <div key={w} className="flex flex-col gap-[3px]">
                {week.map((date, d) => {
                  if (!date) return <span key={d} className="size-3" />;
                  const iso = format(date, "yyyy-MM-dd");
                  const entry = days[iso];
                  return (
                    <span
                      key={d}
                      title={`${format(date, "EEE d MMM")}: ${entry ? `${entry.workouts} workout(s), ${Math.round(kgToDisplay(entry.volume_kg || 0, units))} ${units}` : "rest"}`}
                      className={`size-3 rounded-[3px] ${shades[entry ? level(entry.volume_kg || 0) : 0]}`}
                      data-weekday={getDay(date)}
                    />
                  );
                })}
              </div>
            ))}
          </div>
          <div className="mt-2 flex items-center justify-end gap-1 text-xs text-zinc-500">
            Less
            {shades.map((shade) => (
              <span key={shade} className={`size-3 rounded-[3px] ${shade}`} />
            ))}
            More
          </div>
        </div>
      )}
    </Card>
  );
}

function E1rmTrends({ units }) {
  const data = useQuery({ queryKey: ["insights", "e1rm"], queryFn: () => api("/analytics/e1rm-trends/") });
  if (data.isPending) return <Spinner />;
  if (data.isError) return <ErrorBox error={data.error} />;
  const exercises = data.data.exercises;
  const months = [...new Set(exercises.flatMap((e) => e.points.map((p) => p.month)))].sort();
  const rows = months.map((month) => {
    const row = { month };
    exercises.forEach((e) => {
      const point = e.points.find((p) => p.month === month);
      if (point) row[e.name] = Math.round(kgToDisplay(point.best_e1rm_kg, units));
    });
    return row;
  });

  return (
    <Card>
      <h2 className="mb-3 font-semibold">Estimated 1RM trend ({units}), your top lifts</h2>
      {exercises.length === 0 ? (
        <p className="py-8 text-center text-sm text-zinc-500">No lifts logged in the last year yet.</p>
      ) : (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" strokeOpacity={0.1} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ borderRadius: 12 }} />
              <Legend />
              {exercises.map((e, i) => (
                <Line key={e.exercise_id} dataKey={e.name} stroke={COLORS[i % COLORS.length]} strokeWidth={2} connectNulls dot={{ r: 3 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

export default function Insights() {
  const { user } = useAuth();
  return (
    <div className="space-y-4">
      <PageHeader title="Insights" subtitle="How your training is really going" />
      {user.is_premium ? (
        <>
          <Heatmap units={user.units} />
          <MuscleVolume units={user.units} />
          <E1rmTrends units={user.units} />
        </>
      ) : (
        <PremiumLock title="Insights is a Premium feature">
          See weekly volume per muscle group, a year-long training heatmap and 1RM trends for your main lifts.
        </PremiumLock>
      )}
    </div>
  );
}
