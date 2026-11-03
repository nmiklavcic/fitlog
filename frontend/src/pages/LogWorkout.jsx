import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Dumbbell, Plus, Timer, Trash2, X } from "lucide-react";
import { api } from "../api/client";
import ExercisePicker from "../components/ExercisePicker";
import { Button, Card, Empty, ErrorBox, Field, Input, PageHeader, Textarea } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { clearDraft, loadDraft, newDraft, saveDraft } from "../lib/draft";
import { todayIso } from "../lib/format";
import { inputToKg, kgToDisplay, trimNumber } from "../lib/units";

const uid = () => Math.random().toString(36).slice(2, 10);

export function setsFromKg(sets, units) {
  return sets.map((s) => ({ weight: s.weight_kg ? trimNumber(kgToDisplay(s.weight_kg, units), 2) : "", reps: String(s.reps ?? "") }));
}

export function draftExercise(exercise, previous, sets) {
  return { key: uid(), exercise, previous, sets: sets?.length ? sets : [{ weight: "", reps: "" }] };
}

function Elapsed({ since }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const seconds = Math.max(0, Math.floor((now - new Date(since).getTime()) / 1000));
  const h = Math.floor(seconds / 3600);
  const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
  const s = String(seconds % 60).padStart(2, "0");
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-sm tabular-nums">
      <Timer className="size-4" aria-hidden />
      {h > 0 ? `${h}:` : ""}
      {m}:{s}
    </span>
  );
}

function StartScreen({ onStart }) {
  const [params] = useSearchParams();
  const { user } = useAuth();
  const date = params.get("date") || todayIso();
  const templates = useQuery({ queryKey: ["templates"], queryFn: () => api("/templates/") });
  const fromTemplate = useMutation({
    mutationFn: (id) => api(`/templates/${id}/start/`, { method: "POST" }),
    onSuccess: (data) =>
      onStart(
        newDraft({
          units: user.units,
          date,
          title: data.title,
          templateId: data.template_id,
          exercises: data.exercises.map((e) => draftExercise(e.exercise, e.previous, setsFromKg(e.sets, user.units))),
        })
      ),
  });

  return (
    <div>
      <PageHeader title="Log a workout" subtitle={date === todayIso() ? "Today" : `For ${date}`} />
      <Card className="mb-6 flex flex-col items-center py-10 text-center">
        <Dumbbell className="mb-3 size-10 text-indigo-500" aria-hidden />
        <p className="font-semibold">Ready to train?</p>
        <p className="mb-5 text-sm text-zinc-500">Add exercises as you go. Your progress is saved on this device until you finish.</p>
        <Button size="lg" onClick={() => onStart(newDraft({ units: user.units, date }))}>
          <Plus className="size-5" /> Start empty workout
        </Button>
      </Card>
      <h2 className="mb-3 font-semibold">Start from a template</h2>
      <ErrorBox error={fromTemplate.error} className="mb-3" />
      {templates.data?.length ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {templates.data.map((template) => (
            <button
              key={template.id}
              type="button"
              onClick={() => fromTemplate.mutate(template.id)}
              disabled={fromTemplate.isPending}
              className="rounded-2xl border border-zinc-200 bg-white p-4 text-left shadow-sm transition hover:border-indigo-300 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <p className="font-medium">{template.name}</p>
              <p className="mt-1 line-clamp-2 text-sm text-zinc-500">
                {template.exercises.map((e) => e.exercise.name).join(", ")}
              </p>
            </button>
          ))}
        </div>
      ) : (
        <Empty icon={ClipboardList} title="No templates yet">
          Save a finished workout as a template to reuse it.
        </Empty>
      )}
    </div>
  );
}

function SetRow({ index, set, previous, units, onChange, onRemove, canRemove }) {
  return (
    <div className="grid grid-cols-[2rem_1fr_1fr_1fr_2rem] items-center gap-2">
      <span className="text-center text-sm font-medium text-zinc-500">{index + 1}</span>
      <span className="truncate text-center text-xs text-zinc-400">
        {previous ? `${trimNumber(kgToDisplay(previous.weight_kg, units))}×${previous.reps}` : "-"}
      </span>
      <Input
        inputMode="decimal"
        value={set.weight}
        placeholder={previous ? trimNumber(kgToDisplay(previous.weight_kg, units)) : units}
        onChange={(e) => onChange({ ...set, weight: e.target.value })}
        aria-label={`Set ${index + 1} weight (${units})`}
        className="text-center"
      />
      <Input
        inputMode="numeric"
        value={set.reps}
        placeholder={previous ? String(previous.reps) : "reps"}
        onChange={(e) => onChange({ ...set, reps: e.target.value.replace(/\D/g, "") })}
        aria-label={`Set ${index + 1} reps`}
        className="text-center"
      />
      <button
        type="button"
        onClick={onRemove}
        disabled={!canRemove}
        className="flex justify-center text-zinc-400 hover:text-red-500 disabled:opacity-30"
        aria-label={`Remove set ${index + 1}`}
      >
        <X className="size-4" />
      </button>
    </div>
  );
}

function ExerciseCard({ entry, units, onChange, onRemove }) {
  const updateSet = (i, value) => onChange({ ...entry, sets: entry.sets.map((s, j) => (j === i ? value : s)) });
  const addSet = () => {
    const last = entry.sets[entry.sets.length - 1] ?? { weight: "", reps: "" };
    onChange({ ...entry, sets: [...entry.sets, { ...last }] }); // repeat the last set
  };
  return (
    <Card>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold">{entry.exercise.name}</p>
          {entry.previous && (
            <p className="text-xs text-zinc-500">Last time ({entry.previous.performed_on}): {entry.previous.sets.length} sets</p>
          )}
        </div>
        <button type="button" onClick={onRemove} className="rounded-lg p-1 text-zinc-400 hover:text-red-500" aria-label="Remove exercise">
          <Trash2 className="size-4" />
        </button>
      </div>
      <div className="mb-1 grid grid-cols-[2rem_1fr_1fr_1fr_2rem] gap-2 text-center text-xs font-medium text-zinc-500 uppercase">
        <span>Set</span>
        <span>Previous</span>
        <span>{units}</span>
        <span>Reps</span>
        <span />
      </div>
      <div className="space-y-2">
        {entry.sets.map((set, i) => (
          <SetRow
            key={i}
            index={i}
            set={set}
            units={units}
            previous={entry.previous?.sets[i]}
            onChange={(value) => updateSet(i, value)}
            onRemove={() => onChange({ ...entry, sets: entry.sets.filter((_, j) => j !== i) })}
            canRemove={entry.sets.length > 1}
          />
        ))}
      </div>
      <Button variant="secondary" size="sm" className="mt-3 w-full" onClick={addSet}>
        <Plus className="size-4" /> Add set (repeats the last one)
      </Button>
    </Card>
  );
}

function toPayload(draft) {
  const exercises = draft.exercises
    .map((entry) => ({
      exercise_id: entry.exercise.id,
      sets: entry.sets
        .filter((s) => s.reps !== "" || s.weight !== "")
        .map((s) => ({ weight_kg: inputToKg(s.weight, draft.units) ?? 0, reps: parseInt(s.reps, 10) })),
    }))
    .filter((e) => e.sets.length);
  const invalid = exercises.some((e) => e.sets.some((s) => !s.reps || s.reps < 1 || s.weight_kg < 0));
  return { exercises, invalid };
}

export default function LogWorkout() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(() => loadDraft(user.id));
  const [pickerOpen, setPickerOpen] = useState(false);
  const [problem, setProblem] = useState("");

  const update = (change) =>
    setDraft((current) => {
      const next = typeof change === "function" ? change(current) : change;
      saveDraft(user.id, next);
      return next;
    });

  const save = useMutation({
    mutationFn: (payload) =>
      draft.workoutId
        ? api(`/workouts/${draft.workoutId}/`, { method: "PATCH", body: payload })
        : api("/workouts/", { method: "POST", body: payload }),
    onSuccess: (workout) => {
      clearDraft(user.id);
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      queryClient.invalidateQueries({ queryKey: ["workout", String(workout.id)] });
      queryClient.setQueryData(["workout", String(workout.id)], workout);
      navigate(draft.workoutId ? `/workouts/${workout.id}` : `/share/${workout.id}`, { replace: true });
    },
  });

  if (!draft) return <StartScreen onStart={update} />;

  const addExercise = async (exercise) => {
    const key = uid();
    update((d) => ({ ...d, exercises: [...d.exercises, { ...draftExercise(exercise, null), key }] }));
    // Fetch "last time" so the user sees what to beat (and gets placeholders).
    try {
      const previous = await api(`/exercises/${exercise.id}/last/`);
      if (previous) update((d) => ({ ...d, exercises: d.exercises.map((e) => (e.key === key ? { ...e, previous } : e)) }));
    } catch {
      // not important enough to show an error
    }
  };

  const finish = () => {
    const { exercises, invalid } = toPayload(draft);
    if (!exercises.length) return setProblem("Add at least one exercise with a set.");
    if (invalid) return setProblem("Every set needs a number of reps (and a weight, 0 for bodyweight).");
    setProblem("");
    const payload = { title: draft.title.trim(), performed_on: draft.performed_on, notes: draft.notes ?? "", exercises };
    if (!draft.workoutId && draft.started_at && draft.performed_on === todayIso()) {
      payload.started_at = draft.started_at;
      payload.finished_at = new Date().toISOString();
    }
    save.mutate(payload);
  };

  const discard = () => {
    if (window.confirm(draft.workoutId ? "Discard your changes?" : "Discard this workout?")) {
      clearDraft(user.id);
      setDraft(null);
      if (draft.workoutId) navigate(`/workouts/${draft.workoutId}`);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight">{draft.workoutId ? "Edit workout" : "Workout"}</h1>
        {!draft.workoutId && draft.started_at && draft.performed_on === todayIso() && <Elapsed since={draft.started_at} />}
      </div>
      <Card className="grid gap-3 sm:grid-cols-[1fr_auto]">
        <Field label="Title">
          <Input value={draft.title} onChange={(e) => update({ ...draft, title: e.target.value })} placeholder="e.g. Push day" maxLength={100} />
        </Field>
        <Field label="Date">
          <Input type="date" value={draft.performed_on} max={todayIso()} onChange={(e) => update({ ...draft, performed_on: e.target.value })} />
        </Field>
      </Card>

      {draft.exercises.map((entry) => (
        <ExerciseCard
          key={entry.key}
          entry={entry}
          units={draft.units}
          onChange={(value) => update((d) => ({ ...d, exercises: d.exercises.map((e) => (e.key === entry.key ? value : e)) }))}
          onRemove={() => update((d) => ({ ...d, exercises: d.exercises.filter((e) => e.key !== entry.key) }))}
        />
      ))}

      <Button variant="secondary" size="lg" className="w-full border-2 border-dashed border-zinc-300 dark:border-zinc-700" onClick={() => setPickerOpen(true)}>
        <Plus className="size-5" /> Add exercise
      </Button>

      <Field label="Notes">
        <Textarea rows={2} value={draft.notes ?? ""} onChange={(e) => update({ ...draft, notes: e.target.value })} placeholder="How did it feel?" maxLength={2000} />
      </Field>

      <ErrorBox error={problem || save.error} />
      <div className="flex gap-3">
        <Button variant="ghost" onClick={discard}>
          Discard
        </Button>
        <Button size="lg" className="flex-1" onClick={finish} loading={save.isPending}>
          {draft.workoutId ? "Save changes" : "Finish workout"}
        </Button>
      </div>

      <ExercisePicker open={pickerOpen} onClose={() => setPickerOpen(false)} onSelect={addExercise} />
    </div>
  );
}
