import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Trash2 } from "lucide-react";
import { api } from "../api/client";
import { Button, Card, ErrorBox, Field, Input, PageHeader, PremiumLock, Spinner } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { niceDate, todayIso } from "../lib/format";
import { cmToDisplay, inputToCm, inputToKg, kgToDisplay, lengthUnit, trimNumber } from "../lib/units";

const MEASUREMENTS = [
  ["waist_cm", "Waist"],
  ["chest_cm", "Chest"],
  ["arm_cm", "Arm"],
  ["thigh_cm", "Thigh"],
  ["hips_cm", "Hips"],
];

function CheckIn({ units }) {
  const queryClient = useQueryClient();
  const empty = { measured_on: todayIso(), bodyweight: "", body_fat_pct: "", note: "", ...Object.fromEntries(MEASUREMENTS.map(([k]) => [k, ""])) };
  const [form, setForm] = useState(empty);
  const save = useMutation({
    mutationFn: () => {
      const body = {
        measured_on: form.measured_on,
        bodyweight_kg: form.bodyweight ? Math.round(inputToKg(form.bodyweight, units) * 100) / 100 : null,
        body_fat_pct: form.body_fat_pct ? Math.round(Number(form.body_fat_pct.replace(",", ".")) * 10) / 10 : null,
        note: form.note,
      };
      MEASUREMENTS.forEach(([key]) => {
        body[key] = form[key] ? inputToCm(form[key], units) : null;
      });
      return api("/body-metrics/", { method: "POST", body });
    },
    onSuccess: () => {
      setForm(empty);
      queryClient.invalidateQueries({ queryKey: ["body"] });
    },
  });
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  return (
    <Card>
      <h2 className="mb-3 font-semibold">Check in</h2>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Field label="Date">
            <Input type="date" max={todayIso()} value={form.measured_on} onChange={set("measured_on")} required />
          </Field>
          <Field label={`Bodyweight (${units})`}>
            <Input inputMode="decimal" value={form.bodyweight} onChange={set("bodyweight")} />
          </Field>
          <Field label="Body fat (%)">
            <Input inputMode="decimal" value={form.body_fat_pct} onChange={set("body_fat_pct")} />
          </Field>
          {MEASUREMENTS.map(([key, label]) => (
            <Field key={key} label={`${label} (${lengthUnit(units)})`}>
              <Input inputMode="decimal" value={form[key]} onChange={set(key)} />
            </Field>
          ))}
        </div>
        <Field label="Note">
          <Input value={form.note} onChange={set("note")} maxLength={200} />
        </Field>
        <ErrorBox error={save.error} />
        <Button type="submit" loading={save.isPending}>
          Save check-in
        </Button>
      </form>
    </Card>
  );
}

export default function Body() {
  const { user } = useAuth();
  const units = user.units;
  const queryClient = useQueryClient();
  const enabled = user.is_premium;
  const entries = useQuery({ queryKey: ["body", "list"], queryFn: () => api("/body-metrics/"), enabled });
  const summary = useQuery({ queryKey: ["body", "summary"], queryFn: () => api("/body-metrics/summary/"), enabled });
  const remove = useMutation({
    mutationFn: (id) => api(`/body-metrics/${id}/`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["body"] }),
  });

  if (!enabled) {
    return (
      <div>
        <PageHeader title="Body" />
        <PremiumLock title="Body metrics is a Premium feature">
          Track bodyweight and measurements over time, and see your lifts as a multiple of your bodyweight.
        </PremiumLock>
      </div>
    );
  }

  const chart = [...(entries.data ?? [])]
    .filter((e) => e.bodyweight_kg)
    .reverse()
    .map((e) => ({ date: e.measured_on.slice(5), weight: Number(trimNumber(kgToDisplay(e.bodyweight_kg, units))) }));
  const s = summary.data;

  return (
    <div className="space-y-4">
      <PageHeader title="Body" subtitle="Bodyweight, measurements and relative strength" />
      {s && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Card>
            <p className="text-sm text-zinc-500">Bodyweight</p>
            <p className="text-2xl font-bold">
              {s.latest_bodyweight_kg ? `${trimNumber(kgToDisplay(s.latest_bodyweight_kg, units))} ${units}` : "-"}
            </p>
            {s.change_30d_kg !== null && (
              <p className="text-sm text-zinc-500">
                {s.change_30d_kg > 0 ? "+" : ""}
                {trimNumber(kgToDisplay(s.change_30d_kg, units))} {units} vs. 30 days ago
              </p>
            )}
          </Card>
          <Card>
            <p className="mb-1 text-sm text-zinc-500">Strength ÷ bodyweight (est. 1RM)</p>
            {s.relative_strength.length === 0 ? (
              <p className="text-sm text-zinc-500">Log your bodyweight and some lifts.</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {s.relative_strength.map((r) => (
                  <li key={r.name} className="flex justify-between gap-2">
                    <span className="truncate">{r.name}</span>
                    <span className="font-semibold">{r.ratio}× BW</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
      {chart.length > 1 && (
        <Card>
          <h2 className="mb-3 font-semibold">Bodyweight ({units})</h2>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="currentColor" strokeOpacity={0.1} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={["dataMin - 2", "dataMax + 2"]} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ borderRadius: 12 }} />
                <Line dataKey="weight" stroke="#4f46e5" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}
      <CheckIn units={units} />
      <Card>
        <h2 className="mb-2 font-semibold">History</h2>
        {entries.isPending ? (
          <Spinner />
        ) : (
          <ul className="divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
            {entries.data?.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-3 py-2">
                <span className="text-zinc-500">{niceDate(e.measured_on, "d MMM yyyy")}</span>
                <span className="flex-1 truncate text-right">
                  {e.bodyweight_kg && <b>{trimNumber(kgToDisplay(e.bodyweight_kg, units))} {units}</b>}
                  {MEASUREMENTS.filter(([k]) => e[k]).map(([k, label]) => (
                    <span key={k} className="ml-2 text-zinc-500">
                      {label} {trimNumber(cmToDisplay(e[k], units))}
                    </span>
                  ))}
                </span>
                <button type="button" onClick={() => remove.mutate(e.id)} className="text-zinc-400 hover:text-red-500" aria-label="Delete entry">
                  <Trash2 className="size-4" />
                </button>
              </li>
            ))}
            {entries.data?.length === 0 && <li className="py-4 text-center text-zinc-500">No check-ins yet.</li>}
          </ul>
        )}
      </Card>
    </div>
  );
}
