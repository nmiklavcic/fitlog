import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import QRCode from "qrcode";
import { Crown, Download, ShieldCheck, Trash2 } from "lucide-react";
import { api, fieldErrors } from "../api/client";
import { Avatar, Badge, Button, ButtonLink, Card, ErrorBox, Field, Input, Notice, Select, Textarea, Toggle } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { niceDate } from "../lib/format";

function Section({ title, description, children }) {
  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-semibold">{title}</h2>
        {description && <p className="text-sm text-zinc-500">{description}</p>}
      </div>
      {children}
    </Card>
  );
}

function ProfileSection() {
  const { user, setUser } = useAuth();
  const fileInput = useRef(null);
  const [form, setForm] = useState({
    bio: user.bio,
    is_public: user.is_public,
    units: user.units,
    show_on_leaderboards: user.show_on_leaderboards,
  });
  const save = useMutation({ mutationFn: () => api("/auth/me/", { method: "PATCH", body: form }), onSuccess: setUser });
  const avatar = useMutation({
    mutationFn: (file) => {
      const data = new FormData();
      data.append("photo", file);
      return api("/auth/me/avatar/", { method: "POST", form: data });
    },
    onSuccess: setUser,
  });
  const removeAvatar = useMutation({ mutationFn: () => api("/auth/me/avatar/", { method: "DELETE" }), onSuccess: setUser });

  return (
    <Section title="Profile">
      <div className="flex items-center gap-4">
        <Avatar src={user.avatar?.thumb} name={user.username} size={64} />
        <input
          ref={fileInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && avatar.mutate(e.target.files[0])}
        />
        <Button variant="secondary" size="sm" loading={avatar.isPending} onClick={() => fileInput.current?.click()}>
          Change photo
        </Button>
        {user.avatar && (
          <Button variant="ghost" size="sm" loading={removeAvatar.isPending} onClick={() => removeAvatar.mutate()}>
            Remove
          </Button>
        )}
      </div>
      <ErrorBox error={avatar.error} />
      <Field label="Bio">
        <Textarea rows={2} maxLength={300} value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} />
      </Field>
      <Field label="Units">
        <Select value={form.units} onChange={(e) => setForm({ ...form, units: e.target.value })}>
          <option value="kg">Kilograms (kg, cm)</option>
          <option value="lb">Pounds (lb, in)</option>
        </Select>
      </Field>
      <Toggle
        checked={form.is_public}
        onChange={(v) => setForm({ ...form, is_public: v })}
        label="Public account"
        description="Public: anyone can see your posts. Private: only friends. Your calendar is always private."
      />
      <Toggle
        checked={form.show_on_leaderboards}
        onChange={(v) => setForm({ ...form, show_on_leaderboards: v })}
        label="Show me on friends' leaderboards"
        description="Only weekly totals (volume, workouts, PRs) are shared, and only with friends."
      />
      <ErrorBox error={save.error} />
      {save.isSuccess && <Notice>Saved.</Notice>}
      <Button loading={save.isPending} onClick={() => save.mutate()}>
        Save profile
      </Button>
    </Section>
  );
}

function AccountSection() {
  const { user, setUser } = useAuth();
  const [email, setEmail] = useState(user.email);
  const [emailPassword, setEmailPassword] = useState("");
  const [passwords, setPasswords] = useState({ current_password: "", new_password: "" });

  const saveEmail = useMutation({
    mutationFn: () => api("/auth/me/", { method: "PATCH", body: { email, current_password: emailPassword } }),
    onSuccess: (me) => {
      setUser(me);
      setEmailPassword("");
    },
  });
  const changePassword = useMutation({
    mutationFn: () => api("/auth/password/change/", { method: "POST", body: passwords }),
    onSuccess: () => setPasswords({ current_password: "", new_password: "" }),
  });
  const emailErrors = fieldErrors(saveEmail.error);
  const passwordErrors = fieldErrors(changePassword.error);

  return (
    <Section title="Email and password" description="Changing your password logs out all your other devices.">
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          saveEmail.mutate();
        }}
      >
        <Field label="Email" error={emailErrors.email}>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        {email !== user.email && (
          <Field label="Current password" error={emailErrors.current_password}>
            <Input type="password" value={emailPassword} onChange={(e) => setEmailPassword(e.target.value)} autoComplete="current-password" />
          </Field>
        )}
        {saveEmail.isSuccess && <Notice>Email updated.</Notice>}
        <Button type="submit" variant="secondary" disabled={email === user.email} loading={saveEmail.isPending}>
          Update email
        </Button>
      </form>
      <hr className="border-zinc-200 dark:border-zinc-800" />
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          changePassword.mutate();
        }}
      >
        <Field label="Current password" error={passwordErrors.current_password}>
          <Input
            type="password"
            autoComplete="current-password"
            value={passwords.current_password}
            onChange={(e) => setPasswords({ ...passwords, current_password: e.target.value })}
            required
          />
        </Field>
        <Field label="New password" error={passwordErrors.new_password}>
          <Input
            type="password"
            autoComplete="new-password"
            value={passwords.new_password}
            onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })}
            required
          />
        </Field>
        {changePassword.isSuccess && <Notice>Password changed.</Notice>}
        <Button type="submit" variant="secondary" loading={changePassword.isPending}>
          Change password
        </Button>
      </form>
    </Section>
  );
}

function TwoFactorSection() {
  const { user, setUser, refresh } = useAuth();
  const [setup, setSetup] = useState(null);
  const [qr, setQr] = useState("");
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState(null);
  const [disable, setDisable] = useState({ password: "", code: "" });

  useEffect(() => {
    if (setup) QRCode.toDataURL(setup.otpauth_uri, { margin: 1, width: 200 }).then(setQr);
  }, [setup]);

  const start = useMutation({ mutationFn: () => api("/auth/2fa/setup/", { method: "POST" }), onSuccess: setSetup });
  const confirm = useMutation({
    mutationFn: () => api("/auth/2fa/confirm/", { method: "POST", body: { code } }),
    onSuccess: (data) => {
      setRecoveryCodes(data.recovery_codes);
      setSetup(null);
      setCode("");
      refresh();
    },
  });
  const turnOff = useMutation({
    mutationFn: () => api("/auth/2fa/disable/", { method: "POST", body: disable }),
    onSuccess: (me) => {
      setUser(me);
      setDisable({ password: "", code: "" });
    },
  });
  const disableErrors = fieldErrors(turnOff.error);

  return (
    <Section
      title={
        <span className="flex items-center gap-2">
          <ShieldCheck className="size-5 text-emerald-500" aria-hidden /> Two-factor authentication
          {user.totp_enabled && <Badge tone="green">On</Badge>}
        </span>
      }
      description="Require a 6-digit code from an authenticator app (Google Authenticator, Aegis, 1Password...) when logging in."
    >
      {recoveryCodes && (
        <div className="space-y-2 rounded-xl border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/40">
          <p className="text-sm font-medium">Save these recovery codes now. Each one works once if you lose your phone.</p>
          <ul className="grid grid-cols-2 gap-1 font-mono text-sm">
            {recoveryCodes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <Button size="sm" variant="secondary" onClick={() => setRecoveryCodes(null)}>
            I've saved them
          </Button>
        </div>
      )}

      {user.totp_enabled ? (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            turnOff.mutate();
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Password" error={disableErrors.password}>
              <Input type="password" value={disable.password} onChange={(e) => setDisable({ ...disable, password: e.target.value })} required />
            </Field>
            <Field label="Code" error={disableErrors.code}>
              <Input inputMode="numeric" value={disable.code} onChange={(e) => setDisable({ ...disable, code: e.target.value })} required />
            </Field>
          </div>
          {!Object.keys(disableErrors).length && <ErrorBox error={turnOff.error} />}
          <Button type="submit" variant="secondary" loading={turnOff.isPending}>
            Turn off two-factor
          </Button>
        </form>
      ) : setup ? (
        <div className="space-y-3">
          <p className="text-sm">1. Scan this QR code with your authenticator app:</p>
          {qr && <img src={qr} alt="Two-factor QR code" className="size-48 rounded-lg bg-white p-2" />}
          <p className="text-xs text-zinc-500">
            Or enter this key manually: <code className="font-mono break-all">{setup.secret}</code>
          </p>
          <p className="text-sm">2. Enter the 6-digit code it shows:</p>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              confirm.mutate();
            }}
          >
            <Input inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="123456" className="max-w-40 text-center tracking-widest" />
            <Button type="submit" loading={confirm.isPending}>
              Turn on
            </Button>
          </form>
          <ErrorBox error={confirm.error} />
        </div>
      ) : (
        <>
          <ErrorBox error={start.error} />
          <Button variant="secondary" loading={start.isPending} onClick={() => start.mutate()}>
            Set up two-factor
          </Button>
        </>
      )}
    </Section>
  );
}

function SubscriptionSection() {
  const { user, refresh } = useAuth();
  const billing = useQuery({ queryKey: ["billing"], queryFn: () => api("/billing/status/") });
  const portal = useMutation({
    mutationFn: () => api("/billing/portal/", { method: "POST" }),
    onSuccess: (data) => window.location.assign(data.url),
  });
  const cancelDemo = useMutation({
    mutationFn: () => api("/billing/cancel-demo/", { method: "POST" }),
    onSuccess: () => {
      billing.refetch();
      refresh();
    },
  });
  const sub = billing.data?.subscription;

  return (
    <Section
      title={
        <span className="flex items-center gap-2">
          <Crown className="size-5 text-amber-500" aria-hidden /> Subscription
        </span>
      }
    >
      {user.is_premium && sub ? (
        <div className="space-y-3">
          <p className="text-sm">
            <b>Premium</b> ({sub.plan}) · {sub.cancel_at_period_end || sub.plan === "demo" ? "ends" : "renews"}{" "}
            {sub.current_period_end ? niceDate(sub.current_period_end) : "-"}
          </p>
          {sub.plan === "demo" ? (
            <Button variant="secondary" size="sm" loading={cancelDemo.isPending} onClick={() => cancelDemo.mutate()}>
              End demo subscription
            </Button>
          ) : (
            <Button variant="secondary" size="sm" loading={portal.isPending} onClick={() => portal.mutate()}>
              Manage billing (Stripe)
            </Button>
          )}
        </div>
      ) : (
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-zinc-500">You're on the free plan.</p>
          <ButtonLink to="/premium" variant="premium" size="sm">
            See Premium
          </ButtonLink>
        </div>
      )}
      <ErrorBox error={portal.error || cancelDemo.error} />
    </Section>
  );
}

function DangerSection() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ password: "", code: "" });
  const remove = useMutation({
    mutationFn: () => api("/auth/me/delete/", { method: "POST", body: form }),
    onSuccess: () => {
      queryClient.clear();
      setUser(null);
      navigate("/register", { replace: true });
    },
  });
  const errors = fieldErrors(remove.error);

  return (
    <Section title="Your data" description="Download everything we store about you, or delete your account for good.">
      <a
        href="/api/auth/me/export/"
        className="inline-flex items-center gap-2 rounded-xl bg-zinc-100 px-4 py-2.5 text-sm font-medium hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700"
      >
        <Download className="size-4" aria-hidden /> Download my data (JSON)
      </a>
      <form
        className="space-y-3 rounded-xl border border-red-200 p-3 dark:border-red-900"
        onSubmit={(e) => {
          e.preventDefault();
          if (window.confirm("Delete your account, workouts, posts and photos permanently?")) remove.mutate();
        }}
      >
        <p className="text-sm font-medium text-red-600 dark:text-red-400">Delete account</p>
        <Field label="Password" error={errors.password}>
          <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        </Field>
        {user.totp_enabled && (
          <Field label="Two-factor code" error={errors.code}>
            <Input inputMode="numeric" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
          </Field>
        )}
        {!Object.keys(errors).length && <ErrorBox error={remove.error} />}
        <Button type="submit" variant="danger" loading={remove.isPending}>
          <Trash2 className="size-4" /> Delete my account
        </Button>
      </form>
    </Section>
  );
}

export default function Settings() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
      <ProfileSection />
      <SubscriptionSection />
      <AccountSection />
      <TwoFactorSection />
      <DangerSection />
    </div>
  );
}
