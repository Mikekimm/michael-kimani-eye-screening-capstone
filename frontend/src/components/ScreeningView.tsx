import { History, RefreshCw, Siren } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useModels, useScreeningImage } from "@/hooks/queries";
import { useAuth } from "@/hooks/useAuth";
import type { ModelInfo, ReferralReason, ReviewAction, Screening } from "@/lib/api/types";
import { CONDITION_LABEL, EYE_LABEL, formatDateTime, waitingFor } from "@/lib/utils";

import { Disclaimer, StatusPill } from "./feedback";
import { ScreeningResultCard } from "./ScreeningResultCard";
import { Badge, Card, CardContent, CardHeader, CardTitle, Skeleton, buttonVariants } from "./ui/primitives";

const ACTION_LABEL: Record<ReviewAction, string> = {
  approve: "Approved the screening result",
  override: "Overrode the result",
  request_retake: "Requested a new photo",
  comment: "Commented",
};

// The app's recommendation at the moment the health worker asked (it also sets the review priority).
const ASKED_WHEN: Record<ReferralReason, string> = {
  positive: "referral was recommended",
  uncertain: "the result was uncertain",
  manual: "no referral was needed, but the health worker wanted a second opinion",
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
                    ` (${CONDITION_LABEL[event.condition] ?? event.condition}: ${event.override_positive ? "signs present" : "no signs"})`}
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

/** Saved results are never re-scored. When the installed models have changed since, say so plainly. */
export function OutdatedModelNotice({ screening, models, canRescreen }: {
  screening: Screening; models: ModelInfo[]; canRescreen: boolean;
}) {
  const current = models.filter((m) => m.available && m.version);
  const outdated = screening.results.filter((r) => {
    const model = current.find((m) => m.condition === r.condition);
    return model !== undefined && model.version !== r.model_version;
  });
  if (outdated.length === 0) return null;
  const label = (condition: string) => CONDITION_LABEL[condition] ?? condition;
  const earlier = outdated.filter((r) => r.model_version).map((r) => `${label(r.condition)} ${r.model_version}`);
  const missing = outdated.filter((r) => !r.model_version).map((r) => label(r.condition));
  return (
    <Card data-testid="outdated-model-notice" role="note" className="flex flex-col gap-2 border-risk-medium p-3 text-sm">
      <p className="flex items-center gap-2 font-medium"><RefreshCw aria-hidden className="h-4 w-4" />Made with earlier models</p>
      <p>
        {earlier.length > 0 && <>This result was made by an earlier model ({earlier.join(", ")}). </>}
        {missing.length > 0 && <>No model was installed for {missing.join(" and ")} at the time. </>}
        Current models: {current.map((m) => `${label(m.condition)} ${m.version}`).join(", ")}.{" "}
        {canRescreen ? "Screen again to get current results." : "Ask the health worker to screen again for current results."}
        {" "}This result is kept as it was.
      </p>
      {canRescreen && (
        <Link to={`/screen?patient=${screening.patient_id}`} className={buttonVariants({ size: "sm", variant: "outline" }) + " w-fit"}>
          Screen this patient again
        </Link>
      )}
    </Card>
  );
}

function RetakeNeeded({ screening, canRescreen }: { screening: Screening; canRescreen: boolean }) {
  const request = [...screening.reviews].reverse().find((e) => e.action === "request_retake");
  return (
    <Card role="alert" data-testid="retake-needed" className="flex flex-col gap-2 border-risk-high p-3 text-sm">
      <p className="font-medium">Retake needed</p>
      {request && <p>{request.reviewer_name}: "{request.note}"</p>}
      {canRescreen && (
        <Link to={`/screen?patient=${screening.patient_id}`} className={buttonVariants({ size: "sm" }) + " w-fit"}>
          Take a new photo
        </Link>
      )}
    </Card>
  );
}

function ReviewWaiting({ screening }: { screening: Screening }) {
  if (screening.status !== "referred" || !screening.referred_at) return null;
  return (
    <p data-testid="review-waiting">
      Awaiting specialist for <strong>{waitingFor(screening.referred_at)}</strong> (since {formatDateTime(screening.referred_at)}).{" "}
      {screening.review_overdue
        ? <Badge tone="high">Review overdue</Badge>
        : screening.review_due_at && <>Target: {screening.review_priority} review by {formatDateTime(screening.review_due_at)}.</>}
    </p>
  );
}

export function ScreeningView({ screening }: { screening: Screening }) {
  const models = useModels();
  const { user } = useAuth();
  const isHealthWorker = user?.role === "health_worker";
  const flagged = screening.results.filter((r) => r.refer_suggested).map((r) => r.display_name || CONDITION_LABEL[r.condition]);
  const signsDetected = screening.results.some((r) => r.positive && !r.uncertain);
  return (
    <div className="flex flex-col gap-3">
      <Card className="flex flex-col items-center gap-3 p-4 sm:flex-row sm:items-start">
        <FundusImage id={screening.id} />
        <div className="flex flex-1 flex-col gap-1 text-sm">
          <p className="text-lg font-semibold">{screening.patient_code} · {EYE_LABEL[screening.eye]}</p>
          <StatusPill screening={screening} />
          <p className="text-muted-foreground">Captured {formatDateTime(screening.captured_at)} by {screening.created_by_name}</p>
          {screening.referral_reason && (
            <p>
              Sent to a specialist by {screening.created_by_name} when <strong>{ASKED_WHEN[screening.referral_reason]}</strong>
              {screening.referral_reason !== "manual" && flagged.length > 0 && <> ({flagged.join(", ")})</>}.
            </p>
          )}
          {screening.referral_question && (
            <p data-testid="referral-question" className="rounded-md bg-muted/60 p-2">
              <span className="font-medium">Question for the specialist:</span> {screening.referral_question}
            </p>
          )}
          <ReviewWaiting screening={screening} />
          {screening.quality.warnings.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-risk-medium">{screening.quality.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          )}
        </div>
      </Card>
      <Disclaimer text={screening.disclaimer} />
      {screening.status === "retake_requested" && <RetakeNeeded screening={screening} canRescreen={isHealthWorker} />}
      {isHealthWorker && signsDetected && (
        <Card role="note" className="flex gap-2 p-3 text-sm">
          <Siren aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-risk-high" />
          <p>If the patient has sudden loss of vision, eye pain, or an eye injury, refer them directly by your local
            emergency protocol. Do not wait for the specialist review: this app supports screening and referral and does
            not replace emergency care.</p>
        </Card>
      )}
      {models.data && <OutdatedModelNotice screening={screening} models={models.data} canRescreen={isHealthWorker} />}
      {screening.results.map((result) => (
        <ScreeningResultCard key={result.condition} result={result}
          model={models.data?.find((m) => m.condition === result.condition)} />
      ))}
      <ReviewTimeline screening={screening} />
    </div>
  );
}
