import { useState } from "react";
import { useNavigate } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Play, Plus, Trash2, X } from "lucide-react";
import { api, fieldErrors } from "../api/client";
import ExercisePicker from "../components/ExercisePicker";
import { Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Spinner } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { loadDraft, newDraft, saveDraft } from "../lib/draft";
import { draftExercise, setsFromKg } from "./LogWorkout";

function NewTemplate({ open, onClose }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [items, setItems] = useState([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const create = useMutation({
    mutationFn: () =>
      api("/templates/", {
        method: "POST",
        body: {
          name,
          exercises: items.map((i) => ({ exercise_id: i.exercise.id, target_sets: Number(i.sets) || 3, target_reps: Number(i.reps) || 10 })),
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setName("");
      setItems([]);
      onClose();
    },
  });
  const errors = fieldErrors(create.error);
  const setItem = (index, patch) => setItems((all) => all.map((item, i) => (i === index ? { ...item, ...patch } : item)));

  return (
    <Modal open={open} onClose={onClose} title="New template">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Field label="Name" error={errors.name}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Push day" required />
        </Field>
        <div className="space-y-2">
          {items.map((item, index) => (
            <div key={item.exercise.id + "-" + index} className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{item.exercise.name}</span>
              <Input className="w-16 text-center" inputMode="numeric" value={item.sets} onChange={(e) => setItem(index, { sets: e.target.value })} aria-label="Sets" />
              <span className="text-zinc-400">×</span>
              <Input className="w-16 text-center" inputMode="numeric" value={item.reps} onChange={(e) => setItem(index, { reps: e.target.value })} aria-label="Reps" />
              <button type="button" onClick={() => setItems((all) => all.filter((_, i) => i !== index))} aria-label="Remove">
                <X className="size-4 text-zinc-400" />
              </button>
            </div>
          ))}
        </div>
        <Button variant="secondary" className="w-full" onClick={() => setPickerOpen(true)}>
          <Plus className="size-4" /> Add exercise
        </Button>
        {!errors.name && <ErrorBox error={create.error} />}
        <Button type="submit" className="w-full" disabled={!items.length} loading={create.isPending}>
          Save template
        </Button>
      </form>
      <ExercisePicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(exercise) => setItems((all) => [...all, { exercise, sets: "3", reps: "10" }])}
      />
    </Modal>
  );
}

export default function Templates() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const templates = useQuery({ queryKey: ["templates"], queryFn: () => api("/templates/") });

  const start = useMutation({
    mutationFn: (id) => api(`/templates/${id}/start/`, { method: "POST" }),
    onSuccess: (data) => {
      saveDraft(
        user.id,
        newDraft({
          units: user.units,
          title: data.title,
          templateId: data.template_id,
          exercises: data.exercises.map((e) => draftExercise(e.exercise, e.previous, setsFromKg(e.sets, user.units))),
        })
      );
      navigate("/log");
    },
  });
  const remove = useMutation({
    mutationFn: (id) => api(`/templates/${id}/`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }),
  });

  return (
    <div>
      <PageHeader
        title="Templates"
        subtitle="Reusable routines, pre-filled with your last weights"
        action={
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="size-4" /> New
          </Button>
        }
      />
      <ErrorBox error={start.error || remove.error} className="mb-3" />
      {templates.isPending ? (
        <Spinner />
      ) : templates.data?.length === 0 ? (
        <Empty icon={ClipboardList} title="No templates yet">
          Create one here, or use "Save as template" on any finished workout.
        </Empty>
      ) : (
        <div className="space-y-3">
          {templates.data?.map((template) => (
            <Card key={template.id}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold">{template.name}</p>
                  <ul className="mt-1 space-y-0.5 text-sm text-zinc-500">
                    {template.exercises.map((e) => (
                      <li key={e.id}>
                        {e.target_sets} × {e.target_reps} {e.exercise.name}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button
                    size="sm"
                    loading={start.isPending && start.variables === template.id}
                    onClick={() => {
                      if (loadDraft(user.id) && !window.confirm("Replace the workout you're logging now?")) return;
                      start.mutate(template.id);
                    }}
                  >
                    <Play className="size-4" /> Start
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => window.confirm(`Delete "${template.name}"?`) && remove.mutate(template.id)}
                    aria-label={`Delete ${template.name}`}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
      <NewTemplate open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}
