import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ChartColumn, CircleCheck, Crown, Scale, Sparkles, Trophy } from "lucide-react";
import { api } from "../api/client";
import { Button, ButtonLink, Card, ErrorBox, Notice, Spinner } from "../components/ui";
import { useAuth } from "../hooks/useAuth";

const FEATURES = [
  { icon: ChartColumn, title: "Advanced analytics", text: "All-time progress, weekly volume per muscle group, a training heatmap and 1RM trends.", to: "/insights" },
  { icon: Scale, title: "Body metrics", text: "Track bodyweight and measurements, and see your strength relative to bodyweight.", to: "/body" },
  { icon: Sparkles, title: "Monthly & yearly recaps", text: "Your training summed up in a shareable card.", to: "/recap" },
  { icon: Trophy, title: "Leaderboards & challenges", text: "Weekly friend leaderboards and head-to-head challenges.", to: "/leaderboard" },
];

export default function Premium() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [plan, setPlan] = useState("yearly");
  const billing = useQuery({ queryKey: ["billing"], queryFn: () => api("/billing/status/") });
  const checkout = useMutation({
    mutationFn: () => api("/billing/checkout/", { method: "POST", body: { plan } }),
    // Stripe mode: off to Stripe's hosted checkout page. Demo mode: straight to the success page.
    onSuccess: (data) => window.location.assign(data.url),
  });

  if (billing.isPending) return <Spinner />;
  const prices = billing.data?.prices ?? {};
  const monthlyCost = prices.monthly?.amount ?? 4.99;
  const yearlyCost = prices.yearly?.amount ?? 39.99;
  const saving = Math.round((1 - yearlyCost / (monthlyCost * 12)) * 100);

  return (
    <div className="space-y-6">
      <div className="rounded-3xl bg-linear-to-br from-indigo-600 via-indigo-700 to-zinc-900 px-6 py-10 text-center text-white shadow-lg">
        <Crown className="mx-auto mb-3 size-10 text-amber-300" aria-hidden />
        <h1 className="text-3xl font-bold tracking-tight">Liftlog Premium</h1>
        <p className="mx-auto mt-2 max-w-md text-indigo-100">See exactly how you're progressing, and turn training with friends into a game.</p>
      </div>

      {params.get("canceled") && <Notice>Checkout was canceled. You haven't been charged.</Notice>}

      <div className="grid gap-3 sm:grid-cols-2">
        {FEATURES.map(({ icon: Icon, title, text, to }) => (
          <Card key={title} className="flex gap-3">
            <Icon className="size-6 shrink-0 text-indigo-600 dark:text-indigo-400" aria-hidden />
            <div>
              <p className="font-semibold">{user.is_premium ? <Link to={to} className="hover:underline">{title}</Link> : title}</p>
              <p className="text-sm text-zinc-500">{text}</p>
            </div>
          </Card>
        ))}
      </div>

      {user.is_premium ? (
        <Card className="flex items-center justify-between gap-3">
          <p className="flex items-center gap-2 font-medium">
            <CircleCheck className="size-5 text-emerald-500" aria-hidden /> You have Premium.
          </p>
          <ButtonLink to="/settings" variant="secondary" size="sm">
            Manage
          </ButtonLink>
        </Card>
      ) : (
        <Card className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            {[
              ["monthly", `€${monthlyCost}`, "per month", null],
              ["yearly", `€${yearlyCost}`, "per year", `Save ${saving}%`],
            ].map(([value, price, per, note]) => (
              <button
                key={value}
                type="button"
                onClick={() => setPlan(value)}
                aria-pressed={plan === value}
                className={`rounded-2xl border-2 p-4 text-left transition ${
                  plan === value ? "border-indigo-600 bg-indigo-50 dark:bg-indigo-950/40" : "border-zinc-200 dark:border-zinc-800"
                }`}
              >
                <p className="text-sm font-medium capitalize">{value}</p>
                <p className="text-2xl font-bold">{price}</p>
                <p className="text-xs text-zinc-500">{per}</p>
                {note && <p className="mt-1 text-xs font-semibold text-emerald-600">{note}</p>}
              </button>
            ))}
          </div>
          {billing.data?.mode === "demo" && (
            <Notice>Demo mode: no payment provider is configured, so upgrading is free and lasts 30 days.</Notice>
          )}
          <ErrorBox error={checkout.error} />
          <Button variant="premium" size="lg" className="w-full" loading={checkout.isPending} onClick={() => checkout.mutate()}>
            <Crown className="size-5" /> Upgrade to Premium
          </Button>
          {billing.data?.mode === "stripe" && (
            <p className="text-center text-xs text-zinc-500">
              Secure payment by Stripe. Your card details never reach our servers. Cancel anytime.
            </p>
          )}
        </Card>
      )}
    </div>
  );
}

export function PremiumSuccess() {
  const { refresh } = useAuth();
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const [attempt, setAttempt] = useState(0);
  // After Stripe Checkout, ask the API to sync the session; webhooks may arrive a moment later.
  const status = useQuery({
    queryKey: ["billing", "success", sessionId, attempt],
    queryFn: () => api(`/billing/status/${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`),
  });
  const done = status.data?.is_premium;
  const refreshed = useRef(false);

  useEffect(() => {
    if (done && !refreshed.current) {
      refreshed.current = true;
      refresh(); // reload ["me"] so the whole app sees is_premium
    }
  }, [done, refresh]);
  useEffect(() => {
    if (done || !status.isSuccess || attempt >= 5) return undefined;
    const id = setTimeout(() => setAttempt((a) => a + 1), 2000);
    return () => clearTimeout(id);
  }, [done, status.isSuccess, attempt]);

  return (
    <Card className="flex flex-col items-center py-12 text-center">
      {done ? (
        <>
          <Crown className="mb-3 size-12 text-amber-500" aria-hidden />
          <h1 className="text-2xl font-bold">Welcome to Premium!</h1>
          <p className="mt-1 text-sm text-zinc-500">All Premium features are unlocked.</p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <ButtonLink to="/insights">Open Insights</ButtonLink>
            <ButtonLink to="/recap" variant="secondary">
              See your recap
            </ButtonLink>
          </div>
        </>
      ) : status.isError ? (
        <ErrorBox error={status.error} />
      ) : attempt >= 5 ? (
        <p className="text-sm text-zinc-500">Your payment is still being confirmed. Refresh this page in a minute.</p>
      ) : (
        <>
          <Spinner />
          <p className="text-sm text-zinc-500">Confirming your subscription...</p>
        </>
      )}
    </Card>
  );
}
