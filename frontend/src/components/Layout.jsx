import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  CalendarDays,
  ChartColumn,
  ChartLine,
  ClipboardList,
  Compass,
  Crown,
  Dumbbell,
  House,
  LogOut,
  Menu,
  Plus,
  Scale,
  Settings,
  Sparkles,
  Timer,
  Trophy,
  User,
  Users,
} from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { useHasDraft } from "../lib/draft";
import { Modal } from "./ui";

const mainLinks = [
  { to: "/", label: "Feed", icon: House, end: true },
  { to: "/explore", label: "Explore", icon: Compass },
  { to: "/log", label: "Log workout", icon: Plus },
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
  { to: "/progress", label: "Progress", icon: ChartLine },
  { to: "/templates", label: "Templates", icon: ClipboardList },
  { to: "/friends", label: "Friends", icon: Users },
];
const premiumLinks = [
  { to: "/insights", label: "Insights", icon: ChartColumn },
  { to: "/body", label: "Body", icon: Scale },
  { to: "/recap", label: "Recap", icon: Sparkles },
  { to: "/leaderboard", label: "Leaderboard", icon: Trophy },
];

function useUnreadCount(enabled) {
  const { data } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => api("/notifications/unread-count/"),
    refetchInterval: 30_000, // simple polling: no WebSocket server to deploy
    enabled,
  });
  return data?.count ?? 0;
}

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 text-lg font-bold tracking-tight">
      <span className="rounded-lg bg-indigo-600 p-1.5 text-white">
        <Dumbbell className="size-4" aria-hidden />
      </span>
      Liftlog
    </Link>
  );
}

function SideLink({ to, label, icon: Icon, end, badge, onClick }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition ${
          isActive
            ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
            : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
        }`
      }
    >
      <Icon className="size-5" aria-hidden />
      <span className="flex-1">{label}</span>
      {badge > 0 && (
        <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-xs font-semibold text-white">{badge}</span>
      )}
    </NavLink>
  );
}

function NavSections({ user, unread, onNavigate, onLogout }) {
  return (
    <nav className="space-y-6">
      <div className="space-y-1">
        {mainLinks.map((link) => (
          <SideLink key={link.to} {...link} onClick={onNavigate} />
        ))}
        <SideLink to="/notifications" label="Notifications" icon={Bell} badge={unread} onClick={onNavigate} />
      </div>
      <div className="space-y-1">
        <p className="flex items-center gap-1.5 px-3 text-xs font-semibold tracking-wide text-amber-600 uppercase dark:text-amber-400">
          <Crown className="size-3.5" aria-hidden /> Premium
        </p>
        {premiumLinks.map((link) => (
          <SideLink key={link.to} {...link} onClick={onNavigate} />
        ))}
      </div>
      <div className="space-y-1">
        <SideLink to={`/u/${user.username}`} label="Profile" icon={User} onClick={onNavigate} />
        <SideLink to="/settings" label="Settings" icon={Settings} onClick={onNavigate} />
        {!user.is_premium && <SideLink to="/premium" label="Get Premium" icon={Crown} onClick={onNavigate} />}
        <button
          type="button"
          onClick={onLogout}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
        >
          <LogOut className="size-5" aria-hidden /> Log out
        </button>
      </div>
    </nav>
  );
}

function TabLink({ to, icon: Icon, label, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      aria-label={label}
      className={({ isActive }) =>
        `flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] ${
          isActive ? "text-indigo-600 dark:text-indigo-400" : "text-zinc-500"
        }`
      }
    >
      <Icon className="size-6" aria-hidden />
      {label}
    </NavLink>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const unread = useUnreadCount(Boolean(user));
  const hasDraft = useHasDraft(user?.id);
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = async () => {
    setMenuOpen(false);
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen md:flex">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col gap-8 overflow-y-auto border-r border-zinc-200 bg-white px-4 py-6 md:flex dark:border-zinc-800 dark:bg-zinc-900">
        <div className="px-3">
          <Logo />
        </div>
        <NavSections user={user} unread={unread} onLogout={handleLogout} />
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-zinc-200 bg-white/90 px-4 py-3 backdrop-blur md:hidden dark:border-zinc-800 dark:bg-zinc-900/90">
        <Logo />
        <div className="flex items-center gap-1">
          <Link to="/notifications" className="relative rounded-lg p-2" aria-label="Notifications">
            <Bell className="size-6" />
            {unread > 0 && (
              <span className="absolute top-1 right-1 rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
                {unread}
              </span>
            )}
          </Link>
          <button type="button" className="rounded-lg p-2" onClick={() => setMenuOpen(true)} aria-label="Menu">
            <Menu className="size-6" />
          </button>
        </div>
      </header>
      <Modal open={menuOpen} onClose={() => setMenuOpen(false)} title="Menu">
        <NavSections user={user} unread={unread} onNavigate={() => setMenuOpen(false)} onLogout={handleLogout} />
      </Modal>

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 pt-5 pb-28 md:px-8 md:pt-8 md:pb-12">
        {hasDraft && (
          <Link
            to="/log"
            className="mb-4 flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm"
          >
            <Timer className="size-4" aria-hidden /> Workout in progress - tap to continue
          </Link>
        )}
        <Outlet />
      </main>

      {/* Mobile bottom tabs */}
      <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-zinc-200 bg-white pb-[env(safe-area-inset-bottom)] md:hidden dark:border-zinc-800 dark:bg-zinc-900">
        <TabLink to="/" icon={House} label="Feed" end />
        <TabLink to="/explore" icon={Compass} label="Explore" />
        <TabLink to="/log" icon={Plus} label="Log" />
        <TabLink to="/calendar" icon={CalendarDays} label="Calendar" />
        <TabLink to={`/u/${user.username}`} icon={User} label="Profile" />
      </nav>
    </div>
  );
}
