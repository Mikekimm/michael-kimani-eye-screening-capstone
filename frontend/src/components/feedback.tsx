import { AlertCircle, Inbox, ShieldAlert, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError, NetworkError } from "@/lib/api/http";
import type { ScreeningStatus } from "@/lib/api/types";

import { Badge, Button, Card, Skeleton } from "./ui/primitives";

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <Card className="flex flex-col items-center gap-2 p-8 text-center">
      <Inbox aria-hidden className="h-8 w-8 text-muted-foreground" />
      <p className="font-medium">{title}</p>
      {description && <p className="max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action}
    </Card>
  );
}

export function describeError(error: unknown): string {
  if (error instanceof NetworkError) return "You appear to be offline. Check the connection and try again.";
  if (error instanceof ApiError) return error.message;
  return "Something went wrong. Please try again.";
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const offline = error instanceof NetworkError;
  const Icon = offline ? WifiOff : AlertCircle;
  return (
    <Card role="alert" className="flex flex-col items-center gap-2 p-6 text-center">
      <Icon aria-hidden className="h-7 w-7 text-destructive" />
      <p className="text-sm">{describeError(error)}</p>
      {onRetry && <Button variant="outline" size="sm" onClick={onRetry}>Try again</Button>}
    </Card>
  );
}

export function ListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-label="Loading" role="status">
      {Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-16 w-full" />)}
    </div>
  );
}

const STATUS: Record<ScreeningStatus, { label: string; tone: "neutral" | "low" | "medium" | "high" | "info" }> = {
  completed: { label: "No referral needed", tone: "low" },
  referred: { label: "Awaiting specialist", tone: "medium" },
  reviewed: { label: "Reviewed by specialist", tone: "info" },
  retake_requested: { label: "Retake requested", tone: "high" },
};

export function StatusPill({ status }: { status: ScreeningStatus }) {
  const { label, tone } = STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}

export function Disclaimer({ text }: { text?: string }) {
  return (
    <aside className="flex gap-2 rounded-md border border-risk-medium/30 bg-risk-medium/5 p-3 text-xs text-foreground">
      <ShieldAlert aria-hidden className="h-4 w-4 shrink-0 text-risk-medium" />
      <p>
        {text ?? "Screening support only, not a diagnosis. Results come from a research prototype that has not been clinically validated. A qualified eye-care professional must confirm any finding."}
      </p>
    </aside>
  );
}
