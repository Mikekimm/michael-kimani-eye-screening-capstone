import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronRight } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { z } from "zod";

import { PageHeader } from "@/components/AppShell";
import { EmptyState, ErrorState, ListSkeleton, describeError } from "@/components/feedback";
import { ScreeningView } from "@/components/ScreeningView";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, FieldError, Label, Select, Textarea } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { useReviewQueue, useScreening, useSubmitReview } from "@/hooks/queries";
import type { Screening } from "@/lib/api/types";
import { EYE_LABEL, formatDateTime } from "@/lib/utils";

export function ReviewQueuePage() {
  const queue = useReviewQueue();
  return (
    <>
      <PageHeader title="Review queue" description="Referred screenings, oldest first." />
      {queue.isPending && <ListSkeleton />}
      {queue.isError && <ErrorState error={queue.error} onRetry={() => void queue.refetch()} />}
      {queue.isSuccess && queue.data.length === 0 && <EmptyState title="No cases waiting" description="New referrals appear here after health workers sync." />}
      <div className="flex flex-col gap-2">
        {queue.data?.map((item) => (
          <Link key={item.screening_id} to={`/reviews/${item.screening_id}`}>
            <Card className="flex items-center gap-3 p-3 hover:bg-muted/50">
              <div className="flex flex-1 flex-col gap-1">
                <p className="text-sm font-medium">{item.patient_code} · {EYE_LABEL[item.eye]}</p>
                <p className="text-xs text-muted-foreground">{formatDateTime(item.created_at)} · from {item.created_by_name}</p>
                <div className="flex gap-1">
                  <Badge tone={item.referral_reason === "positive" ? "high" : "medium"}>
                    {item.referral_reason === "uncertain" ? "Borderline" : item.referral_reason === "manual" ? "Manual referral" : "Signs detected"}
                  </Badge>
                  {item.highest_band && <Badge>Band {item.highest_band}</Badge>}
                </div>
              </div>
              <ChevronRight aria-hidden className="h-4 w-4 text-muted-foreground" />
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}

export const reviewSchema = z
  .object({
    action: z.enum(["approve", "override", "request_retake", "comment"]),
    override_positive: z.enum(["", "true", "false"]),
    note: z.string().trim().max(2000),
  })
  .superRefine((value, ctx) => {
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
  const form = useForm<ReviewForm>({ resolver: zodResolver(reviewSchema), defaultValues: { action: "approve", override_positive: "", note: "" } });
  const action = form.watch("action");
  const { errors, isSubmitting } = form.formState;
  const drAvailable = screening.results.some((r) => r.condition === "dr" && r.model_available);

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await submit.mutateAsync({
        action: values.action,
        note: values.note || undefined,
        ...(values.action === "override" ? { condition: "dr", override_positive: values.override_positive === "true" } : {}),
      });
      toast("Review saved.", "success");
      form.reset({ action: "comment", override_positive: "", note: "" });
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
              {drAvailable && <option value="override">Override the DR result</option>}
              <option value="request_retake">Request a new photo</option>
              <option value="comment">Add a comment only</option>
            </Select>
          </div>
          {action === "override" && (
            <div className="flex flex-col gap-1">
              <Label htmlFor="override_positive">Corrected diabetic retinopathy result</Label>
              <Select id="override_positive" aria-invalid={!!errors.override_positive} aria-describedby="override-error" {...form.register("override_positive")}>
                <option value="">Choose...</option>
                <option value="true">Signs of DR present</option>
                <option value="false">No signs of DR</option>
              </Select>
              <FieldError id="override-error" message={errors.override_positive?.message} />
            </div>
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
        <ReviewPanel screening={screening.data} />
      </div>
    </>
  );
}
