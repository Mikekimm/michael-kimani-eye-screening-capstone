import { ArrowLeft, CloudUpload, Loader2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { PageHeader } from "@/components/AppShell";
import { Disclaimer, EmptyState, ErrorState, ListSkeleton, describeError } from "@/components/feedback";
import { ImageCaptureGuide } from "@/components/ImageCaptureGuide";
import { Button, Card, Input, buttonVariants } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { usePatient, usePatients } from "@/hooks/queries";
import { useOnline } from "@/hooks/useOnline";
import { useSync } from "@/hooks/useSync";
import { ApiError, NetworkError } from "@/lib/api/http";
import type { Eye } from "@/lib/api/types";
import { useServices } from "@/lib/services";
import { EYE_LABEL, cn } from "@/lib/utils";

interface ChosenPatient { id?: string; clientUuid?: string; code: string }

function PatientPicker({ onPick }: { onPick: (p: ChosenPatient) => void }) {
  const [q, setQ] = useState("");
  const patients = usePatients(q.trim() || undefined);
  return (
    <div className="flex flex-col gap-2">
      <Input aria-label="Search patients" placeholder="Search by patient code" value={q} onChange={(e) => setQ(e.target.value)} />
      {patients.isPending && <ListSkeleton rows={2} />}
      {patients.isError && <ErrorState error={patients.error} onRetry={() => void patients.refetch()} />}
      {patients.isSuccess && patients.data.length === 0 && (
        <EmptyState title="No patients found" action={<Link to="/patients/new" className={buttonVariants({ size: "sm" })}>Register a patient</Link>} />
      )}
      {patients.data?.map((p) => (
        <Button key={p.id} variant="outline" className="justify-start" onClick={() => onPick({ id: p.id, code: p.code })}>{p.code}</Button>
      ))}
    </div>
  );
}

function PreselectedPatient({ id, onReady }: { id: string; onReady: (p: ChosenPatient) => void }) {
  const patient = usePatient(id);
  if (patient.isPending) return <ListSkeleton rows={1} />;
  if (patient.isError) return <ErrorState error={patient.error} />;
  return <Button onClick={() => onReady({ id: patient.data.id, code: patient.data.code })}>Continue with {patient.data.code}</Button>;
}

export function ScreenPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const online = useOnline();
  const { api, queue } = useServices();
  const { refresh } = useSync();

  const offlinePatient = params.get("offlinePatient");
  const [patient, setPatient] = useState<ChosenPatient | null>(
    offlinePatient ? { clientUuid: offlinePatient, code: params.get("code") ?? "new patient" } : null);
  const [eye, setEye] = useState<Eye | null>(null);
  const [image, setImage] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const saveOffline = async () => {
    await queue.enqueueScreening({ patientId: patient!.id, patientClientUuid: patient!.clientUuid, patientCode: patient!.code,
      eye: eye!, image: image!, patientConsent: true });
    await refresh();
    toast("Saved on this device. It will be analysed when it syncs.", "info");
    navigate("/history");
  };

  const submit = async () => {
    if (!patient || !eye || !image || !consent) return;
    setBusy(true);
    setError(null);
    try {
      // A patient that only exists on the device must sync first, so the screening is queued too.
      if (!online || !patient.id) {
        await saveOffline();
        return;
      }
      const screening = await api.screenings.create({
        patientId: patient.id, eye, image, clientUuid: crypto.randomUUID(), capturedAt: new Date().toISOString(), fileName: image.name,
        patientConsent: consent,
      });
      navigate(`/screenings/${screening.id}`, { replace: true });
    } catch (err) {
      if (err instanceof NetworkError || (err instanceof ApiError && err.status >= 500)) {
        await saveOffline();
      } else {
        setError(describeError(err));
      }
    } finally {
      setBusy(false);
    }
  };

  const step = !patient ? 1 : !eye ? 2 : 3;
  const preselect = params.get("patient");

  return (
    <>
      <PageHeader title="New screening" description={`Step ${step} of 3`} />
      <ol className="mb-4 flex gap-1" aria-label="Progress">
        {[1, 2, 3].map((n) => <li key={n} className={cn("h-1.5 flex-1 rounded-full", n <= step ? "bg-primary" : "bg-muted")} />)}
      </ol>

      {step === 1 && (
        <Card className="p-4">
          <h2 className="mb-3 font-semibold">Choose the patient</h2>
          {preselect ? <PreselectedPatient id={preselect} onReady={setPatient} /> : <PatientPicker onPick={setPatient} />}
        </Card>
      )}

      {step === 2 && (
        <Card className="p-4">
          <h2 className="mb-1 font-semibold">Which eye?</h2>
          <p className="mb-3 text-sm text-muted-foreground">Patient {patient!.code}</p>
          <div className="grid grid-cols-2 gap-2">
            {(["left", "right"] as const).map((side) => (
              <Button key={side} size="lg" variant="outline" onClick={() => setEye(side)}>{EYE_LABEL[side]}</Button>
            ))}
          </div>
          <Button variant="ghost" size="sm" className="mt-3" onClick={() => setPatient(null)}><ArrowLeft aria-hidden className="h-4 w-4" />Change patient</Button>
        </Card>
      )}

      {step === 3 && (
        <Card className="flex flex-col gap-3 p-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">{patient!.code} · {EYE_LABEL[eye!]}</h2>
            <Button variant="ghost" size="sm" onClick={() => { setEye(null); setImage(null); setConsent(false); setError(null); }}>Change eye</Button>
          </div>
          <ImageCaptureGuide onImage={setImage} />
          <label className="flex items-start gap-2 rounded-md border p-3 text-sm">
            <input type="checkbox" className="mt-1 h-4 w-4" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            The patient agreed to have this eye photographed and screened, and to the result being shared with a specialist if needed.
          </label>
          {error && (
            <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</p>
          )}
          <Button size="lg" disabled={!image || !consent || busy} onClick={() => void submit()}>
            {busy ? <><Loader2 aria-hidden className="h-4 w-4 animate-spin" />Uploading and analysing...</>
              : online && patient!.id ? "Analyse photo" : <><CloudUpload aria-hidden className="h-4 w-4" />Save for sync</>}
          </Button>
          {(!online || !patient!.id) && (
            <p className="text-xs text-muted-foreground">
              {online ? "This patient has not synced yet, so" : "You are offline, so"} the photo is saved on this device and analysed after it syncs. No result is shown until then.
            </p>
          )}
          <Disclaimer />
        </Card>
      )}
    </>
  );
}
