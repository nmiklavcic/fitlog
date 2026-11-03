import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { api, fieldErrors } from "../api/client";
import { muscleLabel } from "../lib/format";
import { Badge, Button, ErrorBox, Field, Input, Modal, Select, Spinner } from "./ui";

export const MUSCLES = [
  "abdominals", "abductors", "adductors", "biceps", "calves", "chest", "forearms", "glutes", "hamstrings",
  "lats", "lower back", "middle back", "neck", "quadriceps", "shoulders", "traps", "triceps",
];
const EQUIPMENT = ["barbell", "dumbbell", "cable", "machine", "body only", "kettlebells", "bands", "other"];

export function useDebounced(value, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

function CustomExerciseForm({ initialName, onCreated, onCancel }) {
  const [form, setForm] = useState({ name: initialName, equipment: "barbell", muscle: "chest" });
  const create = useMutation({
    mutationFn: () =>
      api("/exercises/", {
        method: "POST",
        body: { name: form.name, equipment: form.equipment, category: "strength", primary_muscles: [form.muscle] },
      }),
    onSuccess: onCreated,
  });
  const errors = fieldErrors(create.error);
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <p className="text-sm text-zinc-500">Custom exercises are private to you.</p>
      <Field label="Name" error={errors.name}>
        <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoFocus />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Equipment">
          <Select value={form.equipment} onChange={(e) => setForm({ ...form, equipment: e.target.value })}>
            {EQUIPMENT.map((item) => (
              <option key={item} value={item}>
                {muscleLabel(item)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Main muscle">
          <Select value={form.muscle} onChange={(e) => setForm({ ...form, muscle: e.target.value })}>
            {MUSCLES.map((muscle) => (
              <option key={muscle} value={muscle}>
                {muscleLabel(muscle)}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      {!errors.name && <ErrorBox error={create.error} />}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>
          Back
        </Button>
        <Button type="submit" loading={create.isPending}>
          Create exercise
        </Button>
      </div>
    </form>
  );
}

export default function ExercisePicker({ open, onClose, onSelect }) {
  const [query, setQuery] = useState("");
  const [muscle, setMuscle] = useState("");
  const [creating, setCreating] = useState(false);
  const debounced = useDebounced(query.trim());

  const params = new URLSearchParams();
  if (debounced) params.set("q", debounced);
  if (muscle) params.set("muscle", muscle);
  const results = useQuery({
    queryKey: ["exercises", debounced, muscle],
    queryFn: () => api(`/exercises/?${params}`),
    enabled: open && !creating,
    staleTime: 5 * 60_000,
  });

  const choose = (exercise) => {
    onSelect(exercise);
    setQuery("");
    setCreating(false);
    onClose();
  };

  return (
    <Modal open={open} onClose={onClose} title={creating ? "New custom exercise" : "Add exercise"}>
      {creating ? (
        <CustomExerciseForm initialName={query} onCreated={choose} onCancel={() => setCreating(false)} />
      ) : (
        <div className="space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute top-3 left-3 size-4 text-zinc-400" aria-hidden />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search 800+ exercises (typos are fine)"
              className="pl-9"
              autoFocus
            />
          </div>
          <Select value={muscle} onChange={(e) => setMuscle(e.target.value)} aria-label="Filter by muscle">
            <option value="">All muscles</option>
            {MUSCLES.map((m) => (
              <option key={m} value={m}>
                {muscleLabel(m)}
              </option>
            ))}
          </Select>
          {results.isPending ? (
            <Spinner />
          ) : (
            <ul className="max-h-[50vh] divide-y divide-zinc-100 overflow-y-auto dark:divide-zinc-800">
              {results.data?.map((exercise) => (
                <li key={exercise.id}>
                  <button
                    type="button"
                    onClick={() => choose(exercise)}
                    className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-2.5 text-left hover:bg-zinc-50 dark:hover:bg-zinc-800"
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{exercise.name}</span>
                      <span className="block text-xs text-zinc-500">
                        {exercise.primary_muscles.map(muscleLabel).join(", ")}
                        {exercise.equipment && ` · ${exercise.equipment}`}
                      </span>
                    </span>
                    {exercise.is_custom && <Badge tone="indigo">Custom</Badge>}
                  </button>
                </li>
              ))}
              {results.data?.length === 0 && <li className="py-6 text-center text-sm text-zinc-500">No matches.</li>}
            </ul>
          )}
          <ErrorBox error={results.error} />
          <Button variant="secondary" className="w-full" onClick={() => setCreating(true)}>
            <Plus className="size-4" /> Create a custom exercise
          </Button>
        </div>
      )}
    </Modal>
  );
}
