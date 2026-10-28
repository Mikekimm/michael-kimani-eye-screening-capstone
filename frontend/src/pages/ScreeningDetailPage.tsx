import { Check, Send, Trash2 } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { PageHeader } from "@/components/AppShell";
import { ErrorState, ListSkeleton, describeError } from "@/components/feedback";
import { ScreeningView } from "@/components/ScreeningView";
import { Button, Card, FieldError, Label, Select, Textarea } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { useAskSpecialist, useDiscardScreening, useScreening } from "@/hooks/queries";
import type { AskSpecialistInput, ReviewPriority, Screening } from "@/lib/api/types";
import { CONDITION_LABEL } from "@/lib/utils";

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

/** "Ask a specialist": which conditions (pre-ticked from borderline or positive results), the question, and
 * routine or urgent (urgent suggested when the app recommends referral). */
export function AskSpecialistForm({ screening, busy, onSubmit, onCancel }: {
  screening: Screening; busy: boolean; onSubmit: (body: AskSpecialistInput) => void; onCancel: () => void;
}) {
  const scored = screening.results.filter((r) => r.model_available);
  const [conditions, setConditions] = useState<string[]>(screening.referral_conditions?.length
    ? screening.referral_conditions : scored.filter((r) => r.refer_suggested).map((r) => r.condition));
  const [question, setQuestion] = useState("");
  const [priority, setPriority] = useState<ReviewPriority>(screening.review_priority ?? screening.suggested_priority ?? "routine");
  const [errors, setErrors] = useState<{ conditions?: string; question?: string }>({});
  const toggle = (condition: string) =>
    setConditions((now) => (now.includes(condition) ? now.filter((c) => c !== condition) : [...now, condition]));
  const send = () => {
    const found = {
      conditions: conditions.length ? undefined : "Tick at least one condition.",
      question: question.trim().length >= 3 ? undefined : "Write at least a few words.",
    };
    setErrors(found);
    if (!found.conditions && !found.question) onSubmit({ question: question.trim(), conditions, priority });
  };
  return (
    <Card className="flex flex-col gap-3 p-3">
      <fieldset className="flex flex-col gap-1" aria-describedby="ask-conditions-error">
        <legend className="text-sm font-medium">What is your question about?</legend>
        {scored.map((r) => (
          <label key={r.condition} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={conditions.includes(r.condition)} onChange={() => toggle(r.condition)} />
            {r.display_name || CONDITION_LABEL[r.condition]}
          </label>
        ))}
        <FieldError id="ask-conditions-error" message={errors.conditions} />
      </fieldset>
      <div className="flex flex-col gap-1">
        <Label htmlFor="question">Your question for the specialist</Label>
        <Textarea id="question" value={question} aria-invalid={!!errors.question} aria-describedby="question-error"
          placeholder="e.g. Is this proliferative? The patient reports blurred vision." onChange={(e) => setQuestion(e.target.value)} />
        <FieldError id="question-error" message={errors.question} />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="priority">How soon?</Label>
        <Select id="priority" value={priority} onChange={(e) => setPriority(e.target.value as ReviewPriority)}>
          <option value="routine">Routine</option>
          <option value="urgent">Urgent</option>
        </Select>
      </div>
      <div className="flex gap-2">
        <Button disabled={busy} onClick={send}>Send to specialist</Button>
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
  // A case the risk policy queued automatically can still get the health worker's question (once).
  const canAddQuestion = screening.status === "referred" && screening.queued_automatically && !screening.referral_question;

  const sendQuestion = async (body: AskSpecialistInput) => {
    try {
      await ask.mutateAsync(body);
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
        <AskSpecialistForm screening={screening} busy={ask.isPending} onSubmit={(body) => void sendQuestion(body)}
          onCancel={() => setOpen(null)} />
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
          {canAddQuestion && (
            <Button variant="outline" onClick={() => setOpen("ask")}>
              <Send aria-hidden className="h-4 w-4" />Add a question
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
