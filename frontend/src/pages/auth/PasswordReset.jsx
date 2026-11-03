import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useMutation } from "@tanstack/react-query";
import { api, fieldErrors } from "../../api/client";
import { Button, ErrorBox, Field, Input, Notice } from "../../components/ui";
import AuthShell from "./AuthShell";

const backToLogin = (
  <Link to="/login" className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">
    Back to log in
  </Link>
);

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const request = useMutation({
    mutationFn: () => api("/auth/password/reset/", { method: "POST", body: { email } }),
  });

  return (
    <AuthShell title="Reset your password" subtitle="We'll email you a link to choose a new one." footer={backToLogin}>
      {request.isSuccess ? (
        <Notice>{request.data.detail}</Notice>
      ) : (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            request.mutate();
          }}
        >
          <Field label="Email">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus required />
          </Field>
          <ErrorBox error={request.error} />
          <Button type="submit" className="w-full" loading={request.isPending}>
            Send reset link
          </Button>
        </form>
      )}
    </AuthShell>
  );
}

export function ResetPassword() {
  const { uid, token } = useParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const confirm = useMutation({
    mutationFn: () => api("/auth/password/reset/confirm/", { method: "POST", body: { uid, token, new_password: password } }),
    onSuccess: () => setTimeout(() => navigate("/login"), 1500),
  });
  const errors = fieldErrors(confirm.error);

  return (
    <AuthShell title="Choose a new password" footer={backToLogin}>
      {confirm.isSuccess ? (
        <Notice>{confirm.data.detail}</Notice>
      ) : (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            confirm.mutate();
          }}
        >
          <Field label="New password" error={errors.new_password} hint="At least 10 characters.">
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              autoFocus
              required
            />
          </Field>
          {!errors.new_password && <ErrorBox error={confirm.error} />}
          <Button type="submit" className="w-full" loading={confirm.isPending}>
            Save password
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
