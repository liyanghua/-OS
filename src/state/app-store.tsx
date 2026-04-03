"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import type {
  ExceptionItem,
  PolicyBoundary,
  ProjectObject,
  RoleView,
} from "@/domain/types";
import { createMockProjects } from "./mock-projects";
import { createMockExceptions } from "./mock-exceptions";
import { createMockPolicyBoundaries } from "./mock-governance";

const STORAGE_KEY = "cos_role_view";

function readStoredRole(): RoleView | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (
      raw === "ceo" ||
      raw === "product_rd_director" ||
      raw === "growth_director" ||
      raw === "visual_director"
    ) {
      return raw;
    }
  } catch {
    /* ignore */
  }
  return null;
}

type AppState = {
  roleView: RoleView;
  projects: ProjectObject[];
  exceptions: ExceptionItem[];
  policyBoundaries: PolicyBoundary[];
};

const defaultProjects = createMockProjects();
const defaultExceptions = createMockExceptions();
const defaultPolicies = createMockPolicyBoundaries();

const defaultState: AppState = {
  roleView: "ceo",
  projects: defaultProjects,
  exceptions: defaultExceptions,
  policyBoundaries: defaultPolicies,
};

type Listener = () => void;

function createAppStore() {
  let state: AppState = { ...defaultState };
  const listeners = new Set<Listener>();

  return {
    subscribe(listener: Listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getSnapshot(): AppState {
      return state;
    },
    getServerSnapshot(): AppState {
      return defaultState;
    },
    setRoleView(role: RoleView) {
      state = { ...state, roleView: role };
      try {
        localStorage.setItem(STORAGE_KEY, role);
      } catch {
        /* ignore */
      }
      listeners.forEach((l) => l());
    },
    initFromStorage() {
      const stored = readStoredRole();
      if (stored) {
        state = { ...state, roleView: stored };
        listeners.forEach((l) => l());
      }
    },
  };
}

const store = createAppStore();

const AppStoreContext = createContext<typeof store | null>(null);

export function AppStoreProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    store.initFromStorage();
  }, []);

  return (
    <AppStoreContext.Provider value={store}>{children}</AppStoreContext.Provider>
  );
}

export function useAppStore(): AppState {
  const s = useContext(AppStoreContext);
  if (!s) {
    throw new Error("useAppStore must be used within AppStoreProvider");
  }
  return useSyncExternalStore(s.subscribe, s.getSnapshot, s.getServerSnapshot);
}

export function useSetRoleView() {
  const s = useContext(AppStoreContext);
  if (!s) {
    throw new Error("useSetRoleView must be used within AppStoreProvider");
  }
  return useCallback((role: RoleView) => s.setRoleView(role), [s]);
}
