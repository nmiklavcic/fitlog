import { useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { useMutation } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useAuth } from "../../hooks/useAuth";
import { Button, ErrorBox, Field, Input } from "../../components/ui";
import AuthShell from "./AuthShell";

function safeNext(value) {
  // Only allow in-app paths, never "//evil.example" or full URLs (open redirect).
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

export default function Login() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [needsCode, setNeedsCode] = useState(false);

  const finish = (me) => {
    setUser(me);
    navigate(next, { replace: true });
  };

  const login = useMutation({
    mutationFn: () => api("/auth/login/", { method: "POST", body: { username, password } }),
    onSuccess: (data) => (data.two_factor_required ? setNeedsCode(true) : finish(data)),
  });
  const verify = useMutation({
    mutationFn: () => api("/auth/login/2fa/", { method: "POST", body: { code } }),
    onSuccess: finish,
    onError: (error) => {
      if (/log in again|expired/i.test(error.message)) {
        setNeedsCode(false);
        setCode("");
      }
    },
  });

  if (user) return <Navigate to={next} replace />;

  if (needsCode) {
    return (
      <AuthShell title="Two-factor check" subtitle="Enter the 6-digit code from your authenticator app.">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            verify.mutate();
          }}
        >
          <Field label="Code" hint="Lost your phone? Enter one of your recovery codes instead.">
            <Input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              inputMode="numeric"
              autoComplete="one-time-code"
              autoFocus
              placeholder="123456"
              className="text-center text-lg tracking-widest"
            />
          </Field>
          <ErrorBox error={verify.error} />
          <Button type="submit" className="w-full" loading={verify.isPending}>
            Verify
          </Button>
          <Button variant="ghost" className="w-full" onClick={() => setNeedsCode(false)}>
            Back
          </Button>
        </form>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Log in to track your training."
      footer={
        <>
          New here?{" "}
          <Link to="/register" className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">
            Create an account
          </Link>
        </>
      }
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
      >
        <Field label="Username or email">
          <Input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
        </Field>
        <Field label="Password">
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </Field>
        <ErrorBox error={login.error} />
        <Button type="submit" className="w-full" loading={login.isPending}>
          Log in
        </Button>
        <p className="text-center text-sm">
          <Link to="/forgot-password" className="text-zinc-500 hover:underline">
            Forgot your password?
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
