import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImagePlus, PartyPopper } from "lucide-react";
import { api } from "../api/client";
import { WorkoutStats } from "../components/Stats";
import { Button, Card, ErrorBox, Field, Spinner, Textarea } from "../components/ui";
import { useAuth } from "../hooks/useAuth";

const MAX_BYTES = 10 * 1024 * 1024;

export default function Share() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const fileInput = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [caption, setCaption] = useState("");
  const [problem, setProblem] = useState("");

  const workout = useQuery({ queryKey: ["workout", id], queryFn: () => api(`/workouts/${id}/`) });

  useEffect(() => {
    if (!file) return undefined;
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const share = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("workout_id", id);
      form.append("caption", caption);
      form.append("photo", file);
      return api("/posts/", { method: "POST", form });
    },
    onSuccess: (post) => {
      queryClient.invalidateQueries({ queryKey: ["posts"] });
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      queryClient.invalidateQueries({ queryKey: ["workout", id] });
      navigate(`/p/${post.id}`, { replace: true });
    },
  });

  if (workout.isPending) return <Spinner />;
  if (workout.isError) return <ErrorBox error={workout.error} />;
  if (workout.data.post_id) return <Navigate to={`/p/${workout.data.post_id}`} replace />;

  const pick = (event) => {
    const chosen = event.target.files?.[0];
    if (!chosen) return;
    if (chosen.size > MAX_BYTES) return setProblem("That photo is larger than 10 MB.");
    setProblem("");
    setFile(chosen);
  };

  return (
    <div className="space-y-4">
      <div className="text-center">
        <PartyPopper className="mx-auto mb-2 size-10 text-amber-500" aria-hidden />
        <h1 className="text-2xl font-bold tracking-tight">Workout saved!</h1>
        <p className="text-sm text-zinc-500">It's in your calendar. Want to share it with a photo?</p>
      </div>

      <Card className="space-y-4">
        <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={pick} />
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          className="flex aspect-square w-full items-center justify-center overflow-hidden rounded-xl border-2 border-dashed border-zinc-300 bg-zinc-50 text-zinc-500 transition hover:border-indigo-400 sm:aspect-[4/3] dark:border-zinc-700 dark:bg-zinc-800/50"
        >
          {preview ? (
            <img src={preview} alt="Selected workout" className="size-full object-cover" />
          ) : (
            <span className="flex flex-col items-center gap-2">
              <ImagePlus className="size-10" aria-hidden />
              <span className="font-medium">Add a workout photo</span>
              <span className="text-xs">JPEG, PNG or WebP · location data is removed</span>
            </span>
          )}
        </button>
        <Field label="Caption">
          <Textarea rows={2} value={caption} onChange={(e) => setCaption(e.target.value)} maxLength={2200} placeholder="New PR on bench!" />
        </Field>
        <WorkoutStats stats={workout.data.summary} units={user.units} />
        <p className="text-xs text-zinc-500">
          {user.is_public ? "Your account is public: everyone can see this post." : "Your account is private: only your friends will see this post."}
        </p>
        <ErrorBox error={problem || share.error} />
        <div className="flex gap-3">
          <Button variant="ghost" onClick={() => navigate(`/workouts/${id}`, { replace: true })}>
            Skip
          </Button>
          <Button className="flex-1" disabled={!file} loading={share.isPending} onClick={() => share.mutate()}>
            Share workout
          </Button>
        </div>
      </Card>
    </div>
  );
}
