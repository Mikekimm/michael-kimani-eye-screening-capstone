import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { z } from "zod";

import { PageHeader } from "@/components/AppShell";
import { EmptyState, ErrorState, ListSkeleton, describeError } from "@/components/feedback";
import { ScreeningView } from "@/components/ScreeningView";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, FieldError, Label, Select, Textarea } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useReviewQueue, useScreening, useSubmitReview, useTakeCase } from "@/hooks/queries";
import type { QueueItem, Screening } from "@/lib/api/types";
import { CONDITION_LABEL, EYE_LABEL, formatDateTime, waitingFor } from "@/lib/utils";

function TakeButton({ screeningId }: { screeningId: string }) {
  const take = useTakeCase(screeningId);
  const toast = useToast();
  return (
    <Button size="sm" variant="outline" disabled={take.isPending}
      onClick={() => take.mutate(undefined, { onSuccess: () => toast("Case taken. Other specialists see it as yours.", "success"),
        onError: (error) => toast(describeError(error), "error") })}>
      Take this case
    </Button>
  );
}

function QueueCard({ item }: { item: QueueItem }) {
  return (
    <Card className="flex items-center gap-3 p-3" data-testid="queue-card">
      <Link to={`/reviews/${item.screening_id}`} className="flex flex-1 items-center gap-3 hover:opacity-80">
              <div className="flex flex-1 flex-col gap-1">
                <p className="text-sm font-medium">{item.patient_code} · {EYE_LABEL[item.eye]}</p>
                <p className="text-xs text-muted-foreground">
                  from {item.created_by_name}{item.created_by_facility ? `, ${item.created_by_facility}` : ""} · waiting{" "}
                  {waitingFor(item.waiting_since)} (since {formatDateTime(item.waiting_since)})
                </p>
                {item.question && <p className="text-sm">"{item.question}"</p>}
                <div className="flex flex-wrap gap-1">
                  <Badge tone={item.referral_reason === "positive" ? "high" : "medium"}>
                    {item.referral_reason === "uncertain" ? "Borderline" : item.referral_reason === "manual" ? "Manual referral" : "Signs detected"}
                  </Badge>
                  {(item.conditions.length ? item.conditions : item.flagged_conditions).map((c) => <Badge key={c}>{CONDITION_LABEL[c] ?? c}</Badge>)}
                  {item.highest_band && <Badge>DR band {item.highest_band}</Badge>}
                  <Badge tone={item.overdue ? "high" : "neutral"}>
                    {item.overdue ? `Overdue (${item.priority} target passed)` : `${item.priority === "urgent" ? "Urgent" : "Routine"}: due ${formatDateTime(item.due_at)}`}
                  </Badge>
                  {item.assigned_to_name && (
                    <Badge tone="info">{item.assigned_to_me ? "Taken by you" : `Taken by ${item.assigned_to_name}`}</Badge>
                  )}
                </div>
              </div>
              <ChevronRight aria-hidden className="h-4 w-4 text-muted-foreground" />
      </Link>
      {!item.assigned_to_name && <TakeButton screeningId={item.screening_id} />}
    </Card>
  );
}

export function ReviewQueuePage() {
  const queue = useReviewQueue();
  const [tab, setTab] = useState<"mine" | "all">("mine");
  const mine = queue.data?.filter((item) => item.matches_my_specialties) ?? [];
  const shown = tab === "mine" ? mine : queue.data ?? [];
  return (
    <>
      <PageHeader title="Review queue"
        description="Cases health workers sent, with their question. Your specialties first; overdue first, then the longest waiting." />
      <div role="tablist" aria-label="Which cases" className="mb-3 flex gap-2">
        <Button role="tab" aria-selected={tab === "mine"} size="sm" variant={tab === "mine" ? "primary" : "outline"} onClick={() => setTab("mine")}>
          My specialties ({mine.length})
        </Button>
        <Button role="tab" aria-selected={tab === "all"} size="sm" variant={tab === "all" ? "primary" : "outline"} onClick={() => setTab("all")}>
          All cases ({queue.data?.length ?? 0})
        </Button>
      </div>
      {queue.isPending && <ListSkeleton />}
      {queue.isError && <ErrorState error={queue.error} onRetry={() => void queue.refetch()} />}
      {queue.isSuccess && shown.length === 0 && (
        <EmptyState title="No cases waiting"
          description={tab === "mine" ? "Nothing for your specialties. Check All cases." : "New cases appear here after health workers sync."} />
      )}
      <div className="flex flex-col gap-2">
        {shown.map((item) => <QueueCard key={item.screening_id} item={item} />)}
      </div>
    </>
  );
}

export const reviewSchema = z
  .object({
    action: z.enum(["approve", "override", "request_retake", "comment"]),
    condition: z.string(),
    override_positive: z.enum(["", "true", "false"]),
    note: z.string().trim().max(2000),
  })
  .superRefine((value, ctx) => {
    if (value.action === "override" && !value.condition) {
      ctx.addIssue({ code: "custom", path: ["condition"], message: "Choose the condition to correct." });
    }
    if (value.action === "override" && value.override_positive === "") {
      ctx.addIssue({ code: "custom", path: ["override_positive"], message: "Choose the corrected result." });
    }
    if (value.action !== "approve" && !value.note) {
      ctx.addIssue({ code: "custom", path: ["note"], message: value.action === "override" ? "A reason is required for an override." : "Please add a note." });
    }
  });

type ReviewForm = z.infer<typeof reviewSchema>;

function ReviewPanel({ screening }: { screening: Screening }) {
  const submit = useSubmitReview(screening.id);
  const toast = useToast();
  // Only results that a model actually produced can be overridden (the server enforces the same rule)
  const scored = screening.results.filter((r) => r.model_available);
  const empty: ReviewForm = { action: "approve", condition: scored[0]?.condition ?? "", override_positive: "", note: "" };
  const form = useForm<ReviewForm>({ resolver: zodResolver(reviewSchema), defaultValues: empty });
  const action = form.watch("action");
  const condition = form.watch("condition");
  const conditionName = (CONDITION_LABEL[condition] ?? condition).toLowerCase();
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await submit.mutateAsync({
        action: values.action,
        note: values.note || undefined,
        ...(values.action === "override" ? { condition: values.condition, override_positive: values.override_positive === "true" } : {}),
      });
      toast("Review saved.", "success");
      form.reset({ ...empty, action: "comment" });
    } catch (error) {
      form.setError("root", { message: describeError(error) });
    }
  });

  return (
    <Card>
      <CardHeader><CardTitle>Your review</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="action">Decision</Label>
            <Select id="action" {...form.register("action")}>
              <option value="approve">Approve the screening result</option>
              {scored.length > 0 && <option value="override">Override a model result</option>}
              <option value="request_retake">Request a new photo</option>
              <option value="comment">Add a comment only</option>
            </Select>
          </div>
          {action === "override" && (
            <>
              <div className="flex flex-col gap-1">
                <Label htmlFor="condition">Condition to correct</Label>
                <Select id="condition" aria-invalid={!!errors.condition} aria-describedby="condition-error" {...form.register("condition")}>
                  {scored.map((r) => <option key={r.condition} value={r.condition}>{r.display_name || CONDITION_LABEL[r.condition]}</option>)}
                </Select>
                <FieldError id="condition-error" message={errors.condition?.message} />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="override_positive">Corrected {conditionName} result</Label>
                <Select id="override_positive" aria-invalid={!!errors.override_positive} aria-describedby="override-error" {...form.register("override_positive")}>
                  <option value="">Choose...</option>
                  <option value="true">Signs of {conditionName} present</option>
                  <option value="false">No signs of {conditionName}</option>
                </Select>
                <FieldError id="override-error" message={errors.override_positive?.message} />
              </div>
            </>
          )}
          <div className="flex flex-col gap-1">
            <Label htmlFor="note">{action === "override" ? "Reason (required)" : action === "approve" ? "Note (optional)" : "Note"}</Label>
            <Textarea id="note" aria-invalid={!!errors.note} aria-describedby="note-error" {...form.register("note")} />
            <FieldError id="note-error" message={errors.note?.message} />
          </div>
          {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
          <Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving..." : "Save review"}</Button>
          <p className="text-xs text-muted-foreground">Reviews are added to the history; earlier entries are never changed.</p>
        </form>
      </CardContent>
    </Card>
  );
}

/** Take the case, or review it if it is yours; a case taken by another specialist is read-only here. */
function CaseActions({ screening }: { screening: Screening }) {
  const { user } = useAuth();
  const open = screening.status === "referred";
  if (open && screening.assigned_to_id && screening.assigned_to_id !== user?.id) {
    return <Card className="p-3 text-sm" role="status">Being reviewed by {screening.assigned_to_name}. You can read the case but not decide it.</Card>;
  }
  return (
    <>
      {open && !screening.assigned_to_id && (
        <Card className="flex items-center justify-between gap-2 p-3 text-sm">
          <span>Nobody has taken this case yet. Taking it shows other specialists that you are reviewing it.</span>
          <TakeButton screeningId={screening.id} />
        </Card>
      )}
      <ReviewPanel screening={screening} />
    </>
  );
}

export function CaseReviewPage() {
  const { id = "" } = useParams();
  const screening = useScreening(id);
  if (screening.isPending) return <ListSkeleton rows={4} />;
  if (screening.isError) return <ErrorState error={screening.error} onRetry={() => void screening.refetch()} />;
  return (
    <>
      <PageHeader title="Case review" />
      <div className="flex flex-col gap-3">
        <ScreeningView screening={screening.data} />
        <CaseActions screening={screening.data} />
      </div>
    </>
  );
}
