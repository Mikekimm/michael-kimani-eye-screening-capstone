import { Camera, UserPlus } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/AppShell";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/feedback";
import { ScreeningListItem } from "@/components/ScreeningListItem";
import { buttonVariants, Card } from "@/components/ui/primitives";
import { useAuth } from "@/hooks/useAuth";
import { useDailyCounts, useNewDecisions, useScreenings } from "@/hooks/queries";
import { useSync } from "@/hooks/useSync";

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <Card className="flex flex-col gap-0.5 p-3">
      <span className="text-2xl font-semibold">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </Card>
  );
}

export function HomePage() {
  const { user } = useAuth();
  const screenings = useScreenings(20);
  const { counts } = useSync();
  const daily = useDailyCounts(1); // today in the clinic's time zone, counted by the server
  const decisions = useNewDecisions();
  const list = screenings.data ?? [];

  return (
    <>
      <PageHeader title={`Hello, ${user?.full_name.split(" ")[0] ?? ""}`} description="Screen a patient or follow up on referrals." />
      <div className="mb-4 grid grid-cols-2 gap-2">
        <Link to="/screen" className={buttonVariants({ size: "lg" })}><Camera aria-hidden className="h-5 w-5" />New screening</Link>
        <Link to="/patients/new" className={buttonVariants({ variant: "outline", size: "lg" })}><UserPlus aria-hidden className="h-5 w-5" />New patient</Link>
      </div>
      <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Link to="/history" data-testid="new-decisions"><Stat label="New decisions" value={decisions.data ? decisions.data.count : "-"} /></Link>
        <Stat label="Screened today" value={daily.data ? daily.data.days.at(-1)?.count ?? 0 : "-"} />
        <Stat label="Awaiting specialist" value={screenings.isSuccess ? list.filter((s) => s.status === "referred").length : "-"} />
        <Stat label="Waiting to sync" value={counts.pending + counts.syncing + counts.failed} />
      </div>
      <h2 className="mb-2 font-semibold">Recent activity</h2>
      {screenings.isPending && <ListSkeleton />}
      {screenings.isError && <ErrorState error={screenings.error} onRetry={() => void screenings.refetch()} />}
      {screenings.isSuccess && list.length === 0 && (
        <EmptyState title="No screenings yet" description="Start by registering a patient and capturing a fundus photo." />
      )}
      <div className="flex flex-col gap-2">
        {list.slice(0, 8).map((s) => <ScreeningListItem key={s.id} screening={s} />)}
      </div>
    </>
  );
}
