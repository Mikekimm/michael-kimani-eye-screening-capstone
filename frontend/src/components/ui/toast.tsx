import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type Tone = "success" | "error" | "info";
interface Toast { id: number; tone: Tone; message: string }

const ToastContext = createContext<((message: string, tone?: Tone) => void) | null>(null);
const ICONS = { success: CheckCircle2, error: TriangleAlert, info: Info };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), []);
  const show = useCallback((message: string, tone: Tone = "info") => {
    const id = Date.now() + Math.random();
    setToasts((all) => [...all.slice(-2), { id, tone, message }]);
    window.setTimeout(() => dismiss(id), tone === "error" ? 8000 : 4000);
  }, [dismiss]);
  const value = useMemo(() => show, [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 top-2 z-50 flex flex-col items-center gap-2 px-4">
        {toasts.map((toast) => {
          const Icon = ICONS[toast.tone];
          return (
            <div key={toast.id} role={toast.tone === "error" ? "alert" : "status"}
              className={cn("pointer-events-auto flex w-full max-w-md items-start gap-2 rounded-md border bg-card p-3 text-sm shadow-md",
                toast.tone === "error" && "border-destructive/40")}>
              <Icon aria-hidden className={cn("mt-0.5 h-4 w-4 shrink-0", toast.tone === "error" ? "text-destructive" : "text-primary")} />
              <p className="flex-1">{toast.message}</p>
              <button aria-label="Dismiss" onClick={() => dismiss(toast.id)} className="text-muted-foreground"><X className="h-4 w-4" /></button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast must be used inside ToastProvider");
  return show;
}
