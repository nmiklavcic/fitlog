import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { SearchX } from "lucide-react";
import Layout from "./components/Layout";
import { ButtonLink, Empty, Spinner } from "./components/ui";
import { useAuth } from "./hooks/useAuth";
import Login from "./pages/auth/Login";
import Register from "./pages/auth/Register";
import { ForgotPassword, ResetPassword } from "./pages/auth/PasswordReset";
import Calendar from "./pages/Calendar";
import Explore from "./pages/Explore";
import Feed from "./pages/Feed";
import Friends from "./pages/Friends";
import LogWorkout from "./pages/LogWorkout";
import Notifications from "./pages/Notifications";
import PostPage from "./pages/PostPage";
import Premium, { PremiumSuccess } from "./pages/Premium";
import Profile from "./pages/Profile";
import Recap from "./pages/Recap";
import Settings from "./pages/Settings";
import Share from "./pages/Share";
import Templates from "./pages/Templates";
import WorkoutDetail from "./pages/WorkoutDetail";

// Pages with charts load the charting library only when opened (smaller first download).
const Progress = lazy(() => import("./pages/Progress"));
const Insights = lazy(() => import("./pages/Insights"));
const Body = lazy(() => import("./pages/Body"));
const Leaderboard = lazy(() => import("./pages/Leaderboard"));

function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner className="min-h-screen items-center" />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  return <Layout />;
}

function NotFound() {
  return (
    <Empty icon={SearchX} title="Page not found">
      <ButtonLink to="/" variant="secondary" size="sm" className="mt-4">
        Go to your feed
      </ButtonLink>
    </Empty>
  );
}

export default function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password/:uid/:token" element={<ResetPassword />} />
        <Route element={<RequireAuth />}>
          <Route index element={<Feed />} />
          <Route path="explore" element={<Explore />} />
          <Route path="p/:id" element={<PostPage />} />
          <Route path="log" element={<LogWorkout />} />
          <Route path="share/:id" element={<Share />} />
          <Route path="calendar" element={<Calendar />} />
          <Route path="workouts/:id" element={<WorkoutDetail />} />
          <Route path="progress" element={<Progress />} />
          <Route path="templates" element={<Templates />} />
          <Route path="u/:username" element={<Profile />} />
          <Route path="friends" element={<Friends />} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="settings" element={<Settings />} />
          <Route path="premium" element={<Premium />} />
          <Route path="premium/success" element={<PremiumSuccess />} />
          <Route path="insights" element={<Insights />} />
          <Route path="body" element={<Body />} />
          <Route path="recap" element={<Recap />} />
          <Route path="leaderboard" element={<Leaderboard />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
