import { Check, Send, Trash2 } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { PageHeader } from "@/components/AppShell";
import { ErrorState, ListSkeleton, describeError } from "@/components/feedback";
import { ScreeningView } from "@/components/ScreeningView";
import { Button, Card, FieldError, Label, Textarea } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { useAskSpecialist, useDiscardScreening, useScreening } from "@/hooks/queries";
import type { Screening } from "@/lib/api/types";

/** A short text box with a confirm button, used for the specialist question and the discard reason. */
function NoteForm({ id, label, placeholder, submitLabel, busy, onSubmit, onCancel }: {
  id: string; label: string; placeholder: string; submitLabel: string; busy: boolean;
  onSubmit: (text: string) => void; onCancel: () => void;
}) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | undefined>();
  return (
    <Card className="flex flex-col gap-2 p-3">
      <Label htmlFor={id}>{label}</Label>
      <Textarea id={id} value={text} placeholder={placeholder} aria-invalid={!!error} aria-describedby={`${id}-error`}
        onChange={(e) => setText(e.target.value)} />
      <FieldError id={`${id}-error`} message={error} />
      <div className="flex gap-2">
        <Button disabled={busy} onClick={() => (text.trim().length >= 3 ? onSubmit(text.trim()) : setError("Write at least a few words."))}>
          {submitLabel}
        </Button>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </Card>
  );
}

function HealthWorkerActions({ screening, fresh }: { screening: Screening; fresh: boolean }) {
  const ask = useAskSpecialist(screening.id);
  const discard = useDiscardScreening(screening.id);
  const toast = useToast();
  const navigate = useNavigate();
  const [open, setOpen] = useState<"ask" | "discard" | null>(null);
  const canAsk = screening.status === "completed";

  const sendQuestion = async (question: string) => {
    try {
      await ask.mutateAsync(question);
      toast("Sent to a specialist. The answer comes back here at the next sync.", "success");
      setOpen(null);
    } catch (error) {
      toast(describeError(error), "error");
    }
  };
  const remove = async (reason: string) => {
    try {
      await discard.mutateAsync(reason);
      toast("Screening discarded. The photo was deleted; the record of the action is kept.", "success");
      navigate("/history", { replace: true });
    } catch (error) {
      toast(describeError(error), "error");
    }
  };

  return (
    <div className="mt-3 flex flex-col gap-2">
      {open === "ask" && (
        <NoteForm id="question" label="Your question for the specialist" placeholder="e.g. Is this proliferative? The patient reports blurred vision."
          submitLabel="Send to specialist" busy={ask.isPending} onSubmit={(q) => void sendQuestion(q)} onCancel={() => setOpen(null)} />
      )}
      {open === "discard" && (
        <NoteForm id="discard-reason" label="Why discard this screening?" placeholder="e.g. Wrong photo uploaded"
          submitLabel="Discard screening" busy={discard.isPending} onSubmit={(r) => void remove(r)} onCancel={() => setOpen(null)} />
      )}
      {open === null && (
        <div className="grid gap-2 sm:grid-cols-3">
          {fresh && (
            <Button onClick={() => { toast("Saved to history.", "success"); navigate("/history"); }}>
              <Check aria-hidden className="h-4 w-4" />Save
            </Button>
          )}
          {canAsk && (
            <Button variant={screening.referral_advice === "none" ? "outline" : "primary"} onClick={() => setOpen("ask")}>
              <Send aria-hidden className="h-4 w-4" />Ask a specialist
            </Button>
          )}
          <Button variant="outline" onClick={() => setOpen("discard")}>
            <Trash2 aria-hidden className="h-4 w-4" />{fresh ? "Discard" : "Remove screening"}
          </Button>
        </div>
      )}
    </div>
  );
}

/** Health worker's view of one screening: the result and recommendation, then their decision. */
export function ScreeningDetailPage() {
  const { id = "" } = useParams();
  const location = useLocation();
  const screening = useScreening(id);
  const fresh = (location.state as { fresh?: boolean } | null)?.fresh === true;

  if (screening.isPending) return <ListSkeleton rows={4} />;
  if (screening.isError) return <ErrorState error={screening.error} onRetry={() => void screening.refetch()} />;

  return (
    <>
      <PageHeader title="Screening result"
        description={screening.data.patient_consent ? "Patient consent recorded" : screening.data.patient_consent === false ? "No patient consent recorded" : undefined} />
      <ScreeningView screening={screening.data} />
      <HealthWorkerActions screening={screening.data} fresh={fresh} />
    </>
  );
}
