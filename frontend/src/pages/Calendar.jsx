import { useState } from "react";
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import {
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameMonth,
  isToday,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import { Camera, ChevronLeft, ChevronRight, Dumbbell, Plus } from "lucide-react";
import { api } from "../api/client";
import { Button, ButtonLink, Card, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { niceDate, todayIso } from "../lib/format";
import { formatVolume } from "../lib/units";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function Calendar() {
  const { user } = useAuth();
  const [month, setMonth] = useState(() => startOfMonth(new Date()));
  const [selected, setSelected] = useState(todayIso());
  const monthKey = format(month, "yyyy-MM");
  const calendar = useQuery({ queryKey: ["calendar", monthKey], queryFn: () => api(`/workouts/calendar/?month=${monthKey}`) });

  const days = eachDayOfInterval({
    start: startOfWeek(month, { weekStartsOn: 1 }),
    end: endOfWeek(endOfMonth(month), { weekStartsOn: 1 }),
  });
  const byDay = calendar.data?.days ?? {};
  const monthWorkouts = Object.values(byDay).flat();
  const selectedWorkouts = byDay[selected] ?? [];

  return (
    <div>
      <PageHeader
        title="Calendar"
        subtitle={`${monthWorkouts.length} workout${monthWorkouts.length === 1 ? "" : "s"} · ${formatVolume(
          monthWorkouts.reduce((sum, w) => sum + w.volume_kg, 0),
          user.units
        )} in ${format(month, "MMMM")}`}
      />
      <Card className="mb-4">
        <div className="mb-3 flex items-center justify-between">
          <Button variant="ghost" size="icon" onClick={() => setMonth((m) => addMonths(m, -1))} aria-label="Previous month">
            <ChevronLeft className="size-5" />
          </Button>
          <h2 className="font-semibold">{format(month, "MMMM yyyy")}</h2>
          <Button variant="ghost" size="icon" onClick={() => setMonth((m) => addMonths(m, 1))} aria-label="Next month">
            <ChevronRight className="size-5" />
          </Button>
        </div>
        <div className="grid grid-cols-7 gap-1 text-center text-xs font-medium text-zinc-500">
          {WEEKDAYS.map((day) => (
            <span key={day} className="py-1">
              {day}
            </span>
          ))}
        </div>
        {calendar.isPending ? (
          <Spinner />
        ) : (
          <div className="grid grid-cols-7 gap-1">
            {days.map((day) => {
              const iso = format(day, "yyyy-MM-dd");
              const workouts = byDay[iso] ?? [];
              const active = workouts.length > 0;
              const posted = workouts.some((w) => w.post_id);
              return (
                <button
                  key={iso}
                  type="button"
                  onClick={() => setSelected(iso)}
                  aria-label={`${niceDate(iso)}: ${workouts.length} workouts`}
                  aria-pressed={selected === iso}
                  className={`relative flex aspect-square flex-col items-center justify-center rounded-xl text-sm transition ${
                    isSameMonth(day, month) ? "" : "opacity-35"
                  } ${active ? "bg-indigo-600 font-semibold text-white" : "hover:bg-zinc-100 dark:hover:bg-zinc-800"} ${
                    selected === iso ? "ring-2 ring-amber-400 ring-offset-2 ring-offset-white dark:ring-offset-zinc-900" : ""
                  } ${isToday(day) && !active ? "font-bold text-indigo-600 dark:text-indigo-400" : ""}`}
                >
                  {format(day, "d")}
                  {workouts.length > 1 && <span className="text-[10px] leading-none">×{workouts.length}</span>}
                  {posted && <Camera className="absolute top-1 right-1 size-3" aria-hidden />}
                </button>
              );
            })}
          </div>
        )}
        <ErrorBox error={calendar.error} />
      </Card>

      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">{niceDate(selected)}</h2>
        {selected <= todayIso() && (
          <ButtonLink to={`/log?date=${selected}`} size="sm" variant="secondary">
            <Plus className="size-4" /> Log for this day
          </ButtonLink>
        )}
      </div>
      {selectedWorkouts.length === 0 ? (
        <p className="text-sm text-zinc-500">Rest day.</p>
      ) : (
        <div className="space-y-2">
          {selectedWorkouts.map((workout) => (
            <Link key={workout.id} to={`/workouts/${workout.id}`}>
              <Card className="flex items-center gap-3 transition hover:border-indigo-300">
                <span className="rounded-xl bg-indigo-50 p-2 text-indigo-600 dark:bg-indigo-950 dark:text-indigo-300">
                  <Dumbbell className="size-5" aria-hidden />
                </span>
                <div className="flex-1">
                  <p className="font-medium">{workout.title || "Workout"}</p>
                  <p className="text-sm text-zinc-500">
                    {workout.exercise_count} exercises · {workout.set_count} sets · {formatVolume(workout.volume_kg, user.units)}
                  </p>
                </div>
                {workout.post_id ? <Camera className="size-4 text-zinc-400" aria-label="Shared" /> : null}
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
