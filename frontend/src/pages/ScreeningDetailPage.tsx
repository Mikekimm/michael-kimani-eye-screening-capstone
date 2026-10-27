import { Send } from "lucide-react";
import { useParams } from "react-router-dom";

import { PageHeader } from "@/components/AppShell";
import { ErrorState, ListSkeleton, describeError } from "@/components/feedback";
import { ScreeningView } from "@/components/ScreeningView";
import { Button } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { useReferScreening, useScreening } from "@/hooks/queries";

/** Health worker's view of one screening, with a manual referral for cases the policy did not refer. */
export function ScreeningDetailPage() {
  const { id = "" } = useParams();
  const screening = useScreening(id);
  const refer = useReferScreening(id);
  const toast = useToast();

  if (screening.isPending) return <ListSkeleton rows={4} />;
  if (screening.isError) return <ErrorState error={screening.error} onRetry={() => void screening.refetch()} />;

  const canRefer = screening.data.status === "completed";
  const onRefer = async () => {
    try {
      await refer.mutateAsync();
      toast("Sent to the specialist review queue.", "success");
    } catch (error) {
      toast(describeError(error), "error");
    }
  };

  return (
    <>
      <PageHeader title="Screening result"
        description={screening.data.patient_consent ? "Patient consent recorded" : screening.data.patient_consent === false ? "No patient consent recorded" : undefined} />
      <ScreeningView screening={screening.data} />
      {canRefer && (
        <Button variant="outline" className="mt-3 w-full" disabled={refer.isPending} onClick={() => void onRefer()}>
          <Send aria-hidden className="h-4 w-4" />Refer to a specialist anyway
        </Button>
      )}
    </>
  );
}
