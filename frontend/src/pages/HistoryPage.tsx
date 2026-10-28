import { CloudOff, RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/AppShell";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/feedback";
import { ScreeningListItem } from "@/components/ScreeningListItem";
import { Badge, Button, Card, Input, Label } from "@/components/ui/primitives";
import { useDailyCounts, useScreenings } from "@/hooks/queries";
import { useOnline } from "@/hooks/useOnline";
import { useSync } from "@/hooks/useSync";
import type { QueueItem, QueueStatus } from "@/offline/repository";
import { EYE_LABEL, cn, formatDate, formatDateTime } from "@/lib/utils";

const STATUS: Record<QueueStatus, { label: string; tone: "neutral" | "low" | "medium" | "high" | "info" }> = {
  pending: { label: "Waiting to sync", tone: "medium" },
  syncing: { label: "Syncing", tone: "info" },
  synced: { label: "Synced", tone: "low" },
  failed: { label: "Needs attention", tone: "high" },
};

function describe(item: QueueItem): string {
  return item.kind === "patient" ? `New patient ${item.patient.code}` : `${item.patientCode} · ${EYE_LABEL[item.eye]}`;
}

function QueueRow({ item }: { item: QueueItem }) {
  const { retry, discard, syncing } = useSync();
  const { label, tone } = STATUS[item.status];
  return (
    <Card className="flex flex-col gap-2 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium">{describe(item)}</p>
        <Badge tone={tone}>{label}</Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        Saved {formatDateTime(item.createdAt)}{item.attempts ? ` · ${item.attempts} attempt${item.attempts === 1 ? "" : "s"}` : ""}
        {item.status === "pending" && item.nextAttemptAt > Date.now() ? ` · next try ${formatDateTime(new Date(item.nextAttemptAt).toISOString())}` : ""}
      </p>
      {item.lastError && <p className="text-xs text-destructive">{item.lastError}</p>}
      {item.status === "failed" && (
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled={syncing} onClick={() => void retry(item.clientUuid)}><RotateCcw aria-hidden className="h-3.5 w-3.5" />Retry</Button>
          <Button size="sm" variant="ghost" onClick={() => { if (window.confirm("Remove this item from the device? It has not been sent.")) void discard(item.clientUuid); }}>
            <Trash2 aria-hidden className="h-3.5 w-3.5" />Remove
          </Button>
        </div>
      )}
    </Card>
  );
}

/** Screenings per day for the last week (server-side, clinic time zone); tapping a day filters the list. */
function DailyCounts({ day, onPick }: { day: string; onPick: (day: string) => void }) {
  const daily = useDailyCounts(7);
  if (!daily.data) return null;
  return (
    <div className="mb-3">
      <ol className="grid grid-cols-7 gap-1" aria-label={`Screenings per day (${daily.data.time_zone})`}>
        {daily.data.days.map((d) => (
          <li key={d.day}>
            <button type="button" onClick={() => onPick(d.day === day ? "" : d.day)} aria-pressed={d.day === day}
              className={cn("flex w-full flex-col items-center rounded-md border p-1 text-xs", d.day === day && "border-primary bg-primary/10")}>
              <span className="font-semibold tabular-nums" data-testid={`count-${d.day}`}>{d.count}</span>
              <span className="text-muted-foreground">{formatDate(`${d.day}T12:00:00`).replace(/,? \d{4}$/, "")}</span>
            </button>
          </li>
        ))}
      </ol>
      <p className="mt-1 text-[11px] text-muted-foreground">Days follow the clinic time zone ({daily.data.time_zone}).</p>
    </div>
  );
}

export function HistoryPage() {
  const online = useOnline();
  const { items, syncing, syncNow, lastReport } = useSync();
  const [day, setDay] = useState("");
  const screenings = useScreenings(100, day || undefined);
  const outstanding = items.filter((i) => i.status !== "synced");

  return (
    <>
      <PageHeader title="History and sync"
        action={<Button size="sm" variant="outline" disabled={!online || syncing} onClick={() => void syncNow()}>
          <RefreshCw aria-hidden className={syncing ? "h-4 w-4 animate-spin" : "h-4 w-4"} />Sync now</Button>} />

      <section className="mb-6">
        <h2 className="mb-2 font-semibold">On this device</h2>
        {!online && (
          <p className="mb-2 flex items-center gap-2 text-sm text-muted-foreground"><CloudOff aria-hidden className="h-4 w-4" />
            Offline. Items will be sent automatically when the connection returns.</p>
        )}
        {lastReport?.offline && online && <p className="mb-2 text-sm text-risk-medium">The server could not be reached. Retrying with increasing delays.</p>}
        {outstanding.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing waiting. Everything captured on this device has been sent.</p>
        ) : (
          <div className="flex flex-col gap-2">{outstanding.map((item) => <QueueRow key={item.clientUuid} item={item} />)}</div>
        )}
      </section>

      <section>
        <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
          <h2 className="font-semibold">Screenings{day && <> on {formatDate(`${day}T12:00:00`)}</>}</h2>
          <div className="flex items-end gap-2">
            <div className="flex flex-col gap-1">
              <Label htmlFor="history-day" className="text-xs">Day</Label>
              <Input id="history-day" type="date" className="h-9 w-40" value={day} onChange={(e) => setDay(e.target.value)} />
            </div>
            {day && <Button size="sm" variant="ghost" onClick={() => setDay("")}>All days</Button>}
          </div>
        </div>
        <DailyCounts day={day} onPick={setDay} />
        {screenings.isPending && <ListSkeleton />}
        {screenings.isError && <ErrorState error={screenings.error} onRetry={() => void screenings.refetch()} />}
        {screenings.isSuccess && screenings.data.length === 0 && <EmptyState title={day ? "No screenings on this day" : "No screenings yet"} />}
        <div className="flex flex-col gap-2">{screenings.data?.map((s) => <ScreeningListItem key={s.id} screening={s} />)}</div>
      </section>
    </>
  );
}
