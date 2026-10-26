import { History } from "lucide-react";
import { useEffect, useState } from "react";

import { useScreeningImage } from "@/hooks/queries";
import type { ReferralReason, ReviewAction, Screening } from "@/lib/api/types";
import { EYE_LABEL, formatDateTime } from "@/lib/utils";

import { Disclaimer, StatusPill } from "./feedback";
import { ScreeningResultCard } from "./ScreeningResultCard";
import { Card, CardContent, CardHeader, CardTitle, Skeleton } from "./ui/primitives";

const ACTION_LABEL: Record<ReviewAction, string> = {
  approve: "Approved the screening result",
  override: "Overrode the result",
  request_retake: "Requested a new photo",
  comment: "Commented",
};

const REFERRAL_TEXT: Record<ReferralReason, string> = {
  positive: "signs were detected",
  uncertain: "the result was borderline",
  manual: "the health worker referred it",
};

function FundusImage({ id }: { id: string }) {
  const image = useScreeningImage(id);
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!image.data) return;
    const objectUrl = URL.createObjectURL(image.data);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [image.data]);
  if (image.isError) return <p className="text-sm text-muted-foreground">Image unavailable.</p>;
  if (!url) return <Skeleton className="aspect-square w-full max-w-xs rounded-full" />;
  return <img src={url} alt="Fundus photo for this screening" className="aspect-square w-full max-w-xs rounded-full object-cover" />;
}

export function ReviewTimeline({ screening }: { screening: Screening }) {
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><History aria-hidden className="h-4 w-4" />Specialist review history</CardTitle></CardHeader>
      <CardContent>
        {screening.reviews.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {screening.status === "referred" ? "Waiting for a specialist." : "No specialist review for this screening."}
          </p>
        ) : (
          <ol className="flex flex-col gap-3 border-l pl-4">
            {screening.reviews.map((event) => (
              <li key={event.id} className="text-sm">
                <p className="font-medium">
                  {ACTION_LABEL[event.action]}
                  {event.action === "override" && event.condition &&
                    ` (${event.condition.toUpperCase()}: ${event.override_positive ? "signs present" : "no signs"})`}
                </p>
                {event.note && <p className="text-muted-foreground">"{event.note}"</p>}
                <p className="text-xs text-muted-foreground">{event.reviewer_name} · {formatDateTime(event.created_at)}</p>
              </li>
            ))}
          </ol>
        )}
        <p className="mt-3 text-xs text-muted-foreground">History is append-only: entries are never edited or deleted.</p>
      </CardContent>
    </Card>
  );
}

export function ScreeningView({ screening }: { screening: Screening }) {
  return (
    <div className="flex flex-col gap-3">
      <Card className="flex flex-col items-center gap-3 p-4 sm:flex-row sm:items-start">
        <FundusImage id={screening.id} />
        <div className="flex flex-1 flex-col gap-1 text-sm">
          <p className="text-lg font-semibold">{screening.patient_code} · {EYE_LABEL[screening.eye]}</p>
          <StatusPill status={screening.status} />
          <p className="text-muted-foreground">Captured {formatDateTime(screening.captured_at)} by {screening.created_by_name}</p>
          {screening.referral_reason && (
            <p>Referred because <strong>{REFERRAL_TEXT[screening.referral_reason]}</strong>.</p>
          )}
          {screening.quality.warnings.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-risk-medium">{screening.quality.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          )}
        </div>
      </Card>
      <Disclaimer text={screening.disclaimer} />
      {screening.results.map((result) => <ScreeningResultCard key={result.condition} result={result} />)}
      <ReviewTimeline screening={screening} />
    </div>
  );
}
