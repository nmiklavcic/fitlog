import { useEffect } from "react";
import { Link } from "react-router";
import { LoaderCircle, Lock, X } from "lucide-react";
import { errorMessage } from "../api/client";

const buttonVariants = {
  primary: "bg-indigo-600 text-white hover:bg-indigo-500 shadow-sm",
  secondary:
    "bg-zinc-100 text-zinc-900 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  ghost: "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800",
  danger: "bg-red-600 text-white hover:bg-red-500",
  premium: "bg-linear-to-r from-amber-400 to-orange-500 text-zinc-950 hover:brightness-105 shadow-sm",
};
const buttonSizes = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2.5 text-sm",
  lg: "px-5 py-3 text-base",
  icon: "p-2",
};

export function Button({ variant = "primary", size = "md", loading = false, className = "", children, ...props }) {
  return (
    <button
      type="button"
      {...props}
      disabled={loading || props.disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 disabled:cursor-not-allowed disabled:opacity-50 ${buttonVariants[variant]} ${buttonSizes[size]} ${className}`}
    >
      {loading && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function ButtonLink({ to, variant = "primary", size = "md", className = "", children }) {
  return (
    <Link
      to={to}
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-medium transition ${buttonVariants[variant]} ${buttonSizes[size]} ${className}`}
    >
      {children}
    </Link>
  );
}

const fieldClass =
  "w-full rounded-xl border border-zinc-300 bg-white px-3 py-2.5 text-sm outline-none transition placeholder:text-zinc-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-zinc-700 dark:bg-zinc-900";

export function Input({ className = "", ...props }) {
  return <input className={`${fieldClass} ${className}`} {...props} />;
}

export function Textarea({ className = "", ...props }) {
  return <textarea className={`${fieldClass} ${className}`} {...props} />;
}

export function Select({ className = "", children, ...props }) {
  return (
    <select className={`${fieldClass} ${className}`} {...props}>
      {children}
    </select>
  );
}

export function Field({ label, error, hint, children }) {
  return (
    <label className="block space-y-1.5">
      {label && <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{label}</span>}
      {children}
      {error ? (
        <span className="block text-sm text-red-600 dark:text-red-400">{error}</span>
      ) : (
        hint && <span className="block text-xs text-zinc-500">{hint}</span>
      )}
    </label>
  );
}

export function Toggle({ checked, onChange, label, description }) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4">
      <span>
        <span className="block text-sm font-medium">{label}</span>
        {description && <span className="block text-xs text-zinc-500">{description}</span>}
      </span>
      <input
        type="checkbox"
        className="peer sr-only"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="relative mt-0.5 h-6 w-11 shrink-0 rounded-full bg-zinc-300 transition peer-checked:bg-indigo-600 peer-focus-visible:outline-2 peer-focus-visible:outline-indigo-500 after:absolute after:top-0.5 after:left-0.5 after:size-5 after:rounded-full after:bg-white after:shadow after:transition peer-checked:after:translate-x-5 dark:bg-zinc-700" />
    </label>
  );
}

export function Card({ className = "", children, ...props }) {
  return (
    <div
      className={`rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function Spinner({ className = "" }) {
  return (
    <div className={`flex justify-center py-10 ${className}`}>
      <LoaderCircle className="size-6 animate-spin text-zinc-400" aria-label="Loading" />
    </div>
  );
}

export function ErrorBox({ error, className = "" }) {
  if (!error) return null;
  return (
    <div
      role="alert"
      className={`rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300 ${className}`}
    >
      {typeof error === "string" ? error : errorMessage(error)}
    </div>
  );
}

export function Notice({ children, className = "" }) {
  return (
    <div
      className={`rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm text-indigo-800 dark:border-indigo-900 dark:bg-indigo-950/50 dark:text-indigo-200 ${className}`}
    >
      {children}
    </div>
  );
}

export function Empty({ icon: Icon, title, children }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      {Icon && <Icon className="mb-3 size-10 text-zinc-300 dark:text-zinc-600" aria-hidden />}
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 text-sm text-zinc-500">{children}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-zinc-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Avatar({ src, name = "", size = 40, className = "" }) {
  const style = { width: size, height: size };
  if (src) {
    return <img src={src} alt="" style={style} className={`shrink-0 rounded-full object-cover ${className}`} />;
  }
  return (
    <div
      style={{ ...style, fontSize: size * 0.4 }}
      className={`flex shrink-0 items-center justify-center rounded-full bg-indigo-100 font-semibold text-indigo-700 uppercase dark:bg-indigo-950 dark:text-indigo-300 ${className}`}
      aria-hidden
    >
      {name.slice(0, 1)}
    </div>
  );
}

export function Badge({ children, tone = "zinc", className = "" }) {
  const tones = {
    zinc: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
    amber: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
    indigo: "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
    green: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]} ${className}`}>
      {children}
    </span>
  );
}

export function Modal({ open, onClose, title, children, wide = false }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        className={`flex max-h-[90vh] w-full flex-col rounded-t-2xl bg-white shadow-xl sm:rounded-2xl dark:bg-zinc-900 ${wide ? "sm:max-w-2xl" : "sm:max-w-md"}`}
      >
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <h2 className="font-semibold">{title}</h2>
          <button type="button" onClick={onClose} className="rounded-lg p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800" aria-label="Close">
            <X className="size-5" />
          </button>
        </div>
        <div className="overflow-y-auto p-4">{children}</div>
      </div>
    </div>
  );
}

// Shown in place of a Premium feature for free users (the API would answer 402 anyway).
export function PremiumLock({ title, children }) {
  return (
    <Card className="flex flex-col items-center px-6 py-10 text-center">
      <div className="mb-3 rounded-full bg-amber-100 p-3 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
        <Lock className="size-6" aria-hidden />
      </div>
      <p className="text-lg font-semibold">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-zinc-500">{children}</p>
      <ButtonLink to="/premium" variant="premium" className="mt-5">
        Upgrade to Premium
      </ButtonLink>
    </Card>
  );
}
