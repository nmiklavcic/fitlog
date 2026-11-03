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
import LogWorkout from "./pages/LogWorkout";
import PostPage from "./pages/PostPage";
import Progress from "./pages/Progress";
import Share from "./pages/Share";
import Templates from "./pages/Templates";
import WorkoutDetail from "./pages/WorkoutDetail";

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
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
