import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { useMutation } from "@tanstack/react-query";
import { api, fieldErrors } from "../../api/client";
import { useAuth } from "../../hooks/useAuth";
import { Button, ErrorBox, Field, Input, Select, Toggle } from "../../components/ui";
import AuthShell from "./AuthShell";

export default function Register() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", password: "", is_public: false, units: "kg" });
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));

  const register = useMutation({
    mutationFn: () => api("/auth/register/", { method: "POST", body: form }),
    onSuccess: (me) => {
      setUser(me);
      navigate("/log", { replace: true });
    },
  });
  const errors = fieldErrors(register.error);

  // Already logged in (but not because we just signed up: that navigates to /log itself).
  if (user && !register.isSuccess) return <Navigate to="/" replace />;

  return (
    <AuthShell
      title="Create your account"
      subtitle="Log lifts, beat PRs, share progress with friends."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">
            Log in
          </Link>
        </>
      }
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          register.mutate();
        }}
      >
        <Field label="Username" error={errors.username} hint="Letters, numbers, dots and underscores.">
          <Input
            value={form.username}
            onChange={(e) => set("username")(e.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </Field>
        <Field label="Email" error={errors.email}>
          <Input type="email" value={form.email} onChange={(e) => set("email")(e.target.value)} autoComplete="email" required />
        </Field>
        <Field label="Password" error={errors.password} hint="At least 10 characters. A short sentence works well.">
          <Input
            type="password"
            value={form.password}
            onChange={(e) => set("password")(e.target.value)}
            autoComplete="new-password"
            required
          />
        </Field>
        <Field label="Weight units">
          <Select value={form.units} onChange={(e) => set("units")(e.target.value)}>
            <option value="kg">Kilograms (kg)</option>
            <option value="lb">Pounds (lb)</option>
          </Select>
        </Field>
        <Toggle
          checked={form.is_public}
          onChange={set("is_public")}
          label="Public account"
          description="Anyone can see your posts. Off: only friends can (you can change this later)."
        />
        {!Object.keys(errors).length && <ErrorBox error={register.error} />}
        <Button type="submit" className="w-full" loading={register.isPending}>
          Create account
        </Button>
      </form>
    </AuthShell>
  );
}
