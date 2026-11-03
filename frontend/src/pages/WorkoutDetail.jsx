import { Link, useNavigate, useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, ClipboardList, Pencil, Trash2, Trophy } from "lucide-react";
import { api } from "../api/client";
import { Badge, Button, ButtonLink, Card, ErrorBox, Notice, Spinner } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { loadDraft, newDraft, saveDraft } from "../lib/draft";
import { niceDate } from "../lib/format";
import { formatVolume, formatWeight } from "../lib/units";
import { draftExercise, setsFromKg } from "./LogWorkout";

export default function WorkoutDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const workout = useQuery({ queryKey: ["workout", id], queryFn: () => api(`/workouts/${id}/`) });

  const remove = useMutation({
    mutationFn: () => api(`/workouts/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      queryClient.invalidateQueries({ queryKey: ["posts"] });
      navigate("/calendar", { replace: true });
    },
  });
  const saveTemplate = useMutation({
    mutationFn: (name) => api(`/workouts/${id}/save-as-template/`, { method: "POST", body: { name } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }),
  });

  if (workout.isPending) return <Spinner />;
  if (workout.isError) return <ErrorBox error={workout.error} />;
  const w = workout.data;

  const edit = () => {
    if (loadDraft(user.id) && !window.confirm("This replaces the workout you're currently logging. Continue?")) return;
    saveDraft(user.id, {
      ...newDraft({
        units: user.units,
        date: w.performed_on,
        title: w.title,
        workoutId: w.id,
        exercises: w.exercises.map((we) => draftExercise(we.exercise, null, setsFromKg(we.sets, user.units))),
      }),
      notes: w.notes,
    });
    navigate("/log");
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm text-zinc-500">{niceDate(w.performed_on)}</p>
        <h1 className="text-2xl font-bold tracking-tight">{w.title || "Workout"}</h1>
        <p className="mt-1 text-sm text-zinc-500">
          {w.summary.set_count} sets · {formatVolume(w.summary.volume_kg, user.units)}
          {w.summary.duration_min ? ` · ${w.summary.duration_min} min` : ""}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {w.post_id ? (
          <ButtonLink to={`/p/${w.post_id}`} variant="secondary" size="sm">
            <Camera className="size-4" /> View post
          </ButtonLink>
        ) : (
          <ButtonLink to={`/share/${w.id}`} size="sm">
            <Camera className="size-4" /> Share
          </ButtonLink>
        )}
        <Button variant="secondary" size="sm" onClick={edit}>
          <Pencil className="size-4" /> Edit
        </Button>
        <Button
          variant="secondary"
          size="sm"
          loading={saveTemplate.isPending}
          onClick={() => {
            const name = window.prompt("Template name", w.title || "My workout");
            if (name) saveTemplate.mutate(name);
          }}
        >
          <ClipboardList className="size-4" /> Save as template
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="text-red-600"
          loading={remove.isPending}
          onClick={() => window.confirm("Delete this workout? Its post is deleted too.") && remove.mutate()}
        >
          <Trash2 className="size-4" /> Delete
        </Button>
      </div>
      {saveTemplate.isSuccess && <Notice>Saved as a template. Find it under Templates.</Notice>}
      <ErrorBox error={remove.error || saveTemplate.error} />

      {w.summary.pr_count > 0 && (
        <Card className="flex items-center gap-3 border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40">
          <Trophy className="size-6 text-amber-500" aria-hidden />
          <p className="text-sm font-medium">
            {w.summary.pr_count} personal record{w.summary.pr_count > 1 ? "s" : ""} in this workout!
          </p>
        </Card>
      )}

      {w.exercises.map((we) => (
        <Card key={we.id}>
          <div className="mb-2 flex items-center justify-between">
            <Link to={`/progress?exercise=${we.exercise.id}`} className="font-semibold hover:underline">
              {we.exercise.name}
            </Link>
            <span className="text-xs text-zinc-500">{we.exercise.primary_muscles.join(", ")}</span>
          </div>
          <ol className="divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
            {we.sets.map((set, i) => (
              <li key={set.id} className="flex items-center justify-between py-1.5">
                <span className="text-zinc-500">Set {i + 1}</span>
                <span className="flex items-center gap-2">
                  {(w.records[set.id] ?? []).map((kind) => (
                    <Badge key={kind} tone="amber">
                      {kind === "weight" ? "Heaviest" : "Best e1RM"}
                    </Badge>
                  ))}
                  <span className="font-medium">
                    {formatWeight(set.weight_kg, user.units, 2)} × {set.reps}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </Card>
      ))}
      {w.notes && (
        <Card>
          <p className="text-sm whitespace-pre-line text-zinc-600 dark:text-zinc-300">{w.notes}</p>
        </Card>
      )}
    </div>
  );
}
