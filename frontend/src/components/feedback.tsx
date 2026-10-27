import { AlertCircle, Inbox, ShieldAlert, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError, NetworkError } from "@/lib/api/http";
import type { ReferralAdvice, Screening, ScreeningStatus } from "@/lib/api/types";

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

type Tone = "neutral" | "low" | "medium" | "high" | "info";

// Before a case is sent, the label is the app's recommendation; only sent cases are "Awaiting specialist".
const ADVICE: Record<ReferralAdvice, { label: string; tone: Tone }> = {
  none: { label: "No referral needed", tone: "low" },
  consider: { label: "Uncertain, consider asking a specialist", tone: "medium" },
  recommended: { label: "Refer recommended", tone: "high" },
};
const SENT: Record<Exclude<ScreeningStatus, "completed">, { label: string; tone: Tone }> = {
  referred: { label: "Awaiting specialist", tone: "info" },
  reviewed: { label: "Reviewed", tone: "low" },
  retake_requested: { label: "Retake needed", tone: "high" },
};

export function statusLabel(screening: Pick<Screening, "status" | "referral_advice">): { label: string; tone: Tone } {
  return screening.status === "completed" ? ADVICE[screening.referral_advice] : SENT[screening.status];
}

export function StatusPill({ screening }: { screening: Pick<Screening, "status" | "referral_advice"> }) {
  const { label, tone } = statusLabel(screening);
  return <Badge tone={tone} data-testid="status-label">{label}</Badge>;
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
