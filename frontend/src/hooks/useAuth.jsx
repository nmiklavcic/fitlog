import { createContext, useContext } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

const AuthContext = createContext(null);

// The logged-in user lives in the query cache under ["me"]; null means logged out.
export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () =>
      api("/auth/me/").catch((error) => {
        if (error.status === 401) return null;
        throw error;
      }),
    staleTime: 60_000,
    retry: false,
  });

  const value = {
    user: me.data ?? null,
    loading: me.isPending,
    setUser: (user) => queryClient.setQueryData(["me"], user),
    refresh: () => queryClient.invalidateQueries({ queryKey: ["me"] }),
    logout: async () => {
      await api("/auth/logout/", { method: "POST" });
      queryClient.clear();
      queryClient.setQueryData(["me"], null);
    },
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
