import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import type { Screening } from "@/lib/api/types";
import { EYE_LABEL, formatDateTime } from "@/lib/utils";

import { StatusPill } from "./feedback";
import { Badge, Card } from "./ui/primitives";

export function ScreeningListItem({ screening, showPatient = true }: { screening: Screening; showPatient?: boolean }) {
  const dr = screening.results.find((r) => r.condition === "dr");
  return (
    <Link to={`/screenings/${screening.id}`} className="block">
      <Card className="flex items-center gap-3 p-3 hover:bg-muted/50">
        <div className="flex flex-1 flex-col gap-1">
          <p className="text-sm font-medium">
            {showPatient && <>{screening.patient_code} · </>}{EYE_LABEL[screening.eye]}
          </p>
          <p className="text-xs text-muted-foreground">
            {formatDateTime(screening.created_at)}
            {dr?.severity_band ? ` · DR band ${dr.severity_band}` : ""}
          </p>
          <div className="flex flex-wrap gap-1">
            <StatusPill screening={screening} />
            {screening.new_decision && <Badge tone="info" data-testid="new-decision">New decision</Badge>}
          </div>
        </div>
        <ChevronRight aria-hidden className="h-4 w-4 text-muted-foreground" />
      </Card>
    </Link>
  );
}
