import { ClipboardList, Eye, History, Home, Info, LogOut, Users, BarChart3, UserCog, WifiOff, RefreshCw, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { useOnline } from "@/hooks/useOnline";
import { useSync } from "@/hooks/useSync";
import type { Role } from "@/lib/api/types";
import { cn, ROLE_LABEL } from "@/lib/utils";

import { ListSkeleton } from "./feedback";
import { Button } from "./ui/primitives";

interface NavItem { to: string; label: string; icon: LucideIcon }

export const NAV: Record<Role, NavItem[]> = {
  health_worker: [
    { to: "/", label: "Home", icon: Home },
    { to: "/patients", label: "Patients", icon: Users },
    { to: "/screen", label: "Screen", icon: Eye },
    { to: "/history", label: "History", icon: History },
    { to: "/about", label: "Model", icon: Info },
  ],
  specialist: [
    { to: "/reviews", label: "Review queue", icon: ClipboardList },
    { to: "/about", label: "Model", icon: Info },
  ],
  admin: [
    { to: "/admin/analytics", label: "Analytics", icon: BarChart3 },
    { to: "/admin/users", label: "Users", icon: UserCog },
    { to: "/about", label: "Model", icon: Info },
  ],
};

export const HOME_FOR: Record<Role, string> = { health_worker: "/", specialist: "/reviews", admin: "/admin/analytics" };

const CONSENT_KEY = "retina.consent.v1";
export const hasConsented = () => localStorage.getItem(CONSENT_KEY) === "yes";
export const recordConsent = () => localStorage.setItem(CONSENT_KEY, "yes");

/** Guards a route by role. Unauthenticated users go to login; wrong roles go to their own home. */
export function ProtectedRoute({ roles }: { roles: Role[] }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="p-4"><ListSkeleton /></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!hasConsented()) return <Navigate to="/consent" replace />;
  if (!roles.includes(user.role)) return <Navigate to={HOME_FOR[user.role]} replace />;
  return <Outlet />;
}

export function OfflineBanner() {
  const online = useOnline();
  if (online) return null;
  return (
    <div role="status" className="flex items-center gap-2 bg-risk-medium px-4 py-2 text-sm text-white">
      <WifiOff aria-hidden className="h-4 w-4" />
      You are offline. You can still capture photos; they are saved on this device and sent when the connection returns.
    </div>
  );
}

function SyncPill() {
  const { counts, syncing, syncNow } = useSync();
  const waiting = counts.pending + counts.syncing;
  const label = syncing ? "Syncing..." : counts.failed ? `${counts.failed} need attention` : waiting ? `${waiting} waiting to sync` : "All synced";
  return (
    <button onClick={() => void syncNow()} disabled={syncing}
      className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium",
        counts.failed ? "border-destructive/40 text-destructive" : waiting ? "border-risk-medium/40 text-risk-medium" : "text-muted-foreground")}>
      <RefreshCw aria-hidden className={cn("h-3.5 w-3.5", syncing && "animate-spin")} />
      {label}
    </button>
  );
}

/** Mobile: top bar + bottom tabs. Desktop (lg+): sidebar. */
export function AppShell() {
  const { user, loading, logout } = useAuth();
  const location = useLocation();
  // The role guards are rendered inside this shell, so it must redirect signed-out visitors itself.
  if (loading) return <div className="p-4"><ListSkeleton /></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  const items = NAV[user.role];

  return (
    <div className="min-h-dvh lg:flex">
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-card p-4 lg:flex">
        <p className="mb-6 flex items-center gap-2 font-semibold text-primary"><Eye aria-hidden className="h-5 w-5" />Retinal Screening</p>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {items.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"}
              className={({ isActive }) => cn("flex items-center gap-2 rounded-md px-3 py-2 text-sm", isActive ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
              <item.icon aria-hidden className="h-4 w-4" />{item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-2 text-sm">
          <p className="font-medium">{user.full_name}</p>
          <p className="text-xs text-muted-foreground">{ROLE_LABEL[user.role]}</p>
          <Button variant="outline" size="sm" onClick={() => void logout()}><LogOut aria-hidden className="h-4 w-4" />Sign out</Button>
        </div>
      </aside>

      <div className="flex min-h-dvh flex-1 flex-col">
        <OfflineBanner />
        <header className="sticky top-0 z-10 flex items-center justify-between gap-2 border-b bg-card/95 px-4 py-2 backdrop-blur">
          <p className="flex items-center gap-2 font-semibold text-primary lg:hidden"><Eye aria-hidden className="h-5 w-5" />RetinaScreen</p>
          <div className="ml-auto flex items-center gap-2">
            {user.role === "health_worker" && <SyncPill />}
            <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Sign out" onClick={() => void logout()}>
              <LogOut aria-hidden className="h-5 w-5" />
            </Button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-4 pb-24 lg:pb-8">
          <Outlet />
        </main>
        <nav aria-label="Main" className="pb-safe fixed inset-x-0 bottom-0 z-10 grid border-t bg-card lg:hidden"
          style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
          {items.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"}
              className={({ isActive }) => cn("flex flex-col items-center gap-0.5 py-2 text-[11px]", isActive ? "text-primary font-semibold" : "text-muted-foreground")}>
              <item.icon aria-hidden className="h-5 w-5" />{item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}
