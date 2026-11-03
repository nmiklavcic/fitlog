import { Dumbbell } from "lucide-react";

export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-linear-to-br from-indigo-50 via-white to-amber-50 px-4 py-10 dark:from-zinc-950 dark:via-zinc-950 dark:to-indigo-950">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 rounded-2xl bg-indigo-600 p-3 text-white shadow-lg shadow-indigo-600/30">
            <Dumbbell className="size-7" aria-hidden />
          </span>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>}
        </div>
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          {children}
        </div>
        {footer && <div className="mt-4 text-center text-sm text-zinc-500">{footer}</div>}
      </div>
    </div>
  );
}
