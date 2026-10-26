import { zodResolver } from "@hookform/resolvers/zod";
import { Camera, ChevronRight, Search, UserPlus } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import { PageHeader } from "@/components/AppShell";
import { EmptyState, ErrorState, ListSkeleton, describeError } from "@/components/feedback";
import { ScreeningListItem } from "@/components/ScreeningListItem";
import { Button, Card, FieldError, Input, Label, Select, buttonVariants } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { useCreatePatient, usePatient, usePatientScreenings, usePatients } from "@/hooks/queries";
import { useSync } from "@/hooks/useSync";
import { NetworkError } from "@/lib/api/http";
import { useServices } from "@/lib/services";
import { formatDate } from "@/lib/utils";

export function PatientsPage() {
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query.trim());
  const patients = usePatients(deferred || undefined);

  return (
    <>
      <PageHeader title="Patients" description="Patients you registered."
        action={<Link to="/patients/new" className={buttonVariants({ size: "sm" })}><UserPlus aria-hidden className="h-4 w-4" />New</Link>} />
      <div className="relative mb-3">
        <Search aria-hidden className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input aria-label="Search by patient code" placeholder="Search by patient code" className="pl-9" value={query}
          onChange={(e) => setQuery(e.target.value)} />
      </div>
      {patients.isPending && <ListSkeleton />}
      {patients.isError && <ErrorState error={patients.error} onRetry={() => void patients.refetch()} />}
      {patients.isSuccess && patients.data.length === 0 && (
        <EmptyState title={deferred ? "No matching patients" : "No patients yet"}
          action={<Link to="/patients/new" className={buttonVariants({ variant: "outline", size: "sm" })}>Register a patient</Link>} />
      )}
      <div className="flex flex-col gap-2">
        {patients.data?.map((p) => (
          <Link key={p.id} to={`/patients/${p.id}`}>
            <Card className="flex items-center gap-3 p-3 hover:bg-muted/50">
              <div className="flex-1">
                <p className="font-medium">{p.code}</p>
                <p className="text-xs text-muted-foreground">
                  {p.screening_count} screening{p.screening_count === 1 ? "" : "s"}
                  {p.last_screened_at ? ` · last ${formatDate(p.last_screened_at)}` : ""}
                </p>
              </div>
              <ChevronRight aria-hidden className="h-4 w-4 text-muted-foreground" />
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}

const thisYear = new Date().getFullYear();

export const patientSchema = z.object({
  code: z.string().trim().regex(/^[A-Za-z0-9][A-Za-z0-9_-]{2,39}$/, "Use 3-40 letters, digits, - or _ (a clinic code, not a name)."),
  year_of_birth: z.union([z.literal(""), z.coerce.number().int().min(1900).max(thisYear, "Year cannot be in the future.")]),
  sex: z.enum(["female", "male", "other", "unknown"]),
  has_diabetes: z.enum(["yes", "no", "unknown"]),
});

export function NewPatientPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const createPatient = useCreatePatient();
  const { queue } = useServices();
  const { refresh } = useSync();
  const form = useForm<z.input<typeof patientSchema>, unknown, z.output<typeof patientSchema>>({
    resolver: zodResolver(patientSchema), defaultValues: { code: "", year_of_birth: "", sex: "unknown", has_diabetes: "unknown" },
  });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (values) => {
    const body = {
      code: values.code, sex: values.sex, client_uuid: crypto.randomUUID(),
      year_of_birth: values.year_of_birth === "" ? null : values.year_of_birth,
      has_diabetes: values.has_diabetes === "unknown" ? null : values.has_diabetes === "yes",
    };
    try {
      const patient = await createPatient.mutateAsync(body);
      toast(`Patient ${patient.code} registered.`, "success");
      navigate(`/patients/${patient.id}`);
    } catch (error) {
      if (error instanceof NetworkError) {
        await queue.enqueuePatient(body);
        await refresh();
        toast(`Offline: ${body.code} saved on this device and will sync later.`, "info");
        navigate(`/screen?offlinePatient=${body.client_uuid}&code=${encodeURIComponent(body.code)}`);
        return;
      }
      form.setError("root", { message: describeError(error) });
    }
  });

  return (
    <>
      <PageHeader title="Register patient" description="Use a clinic code. Do not enter names or phone numbers." />
      <Card className="p-4">
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="code">Patient code</Label>
            <Input id="code" placeholder="e.g. PHC-0042" aria-invalid={!!errors.code} aria-describedby="code-error" {...form.register("code")} />
            <FieldError id="code-error" message={errors.code?.message} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="year_of_birth">Year of birth</Label>
              <Input id="year_of_birth" inputMode="numeric" placeholder="optional" aria-invalid={!!errors.year_of_birth}
                aria-describedby="yob-error" {...form.register("year_of_birth")} />
              <FieldError id="yob-error" message={errors.year_of_birth?.message} />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="sex">Sex</Label>
              <Select id="sex" {...form.register("sex")}>
                <option value="unknown">Not recorded</option><option value="female">Female</option>
                <option value="male">Male</option><option value="other">Other</option>
              </Select>
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="has_diabetes">Known diabetes</Label>
            <Select id="has_diabetes" {...form.register("has_diabetes")}>
              <option value="unknown">Unknown</option><option value="yes">Yes</option><option value="no">No</option>
            </Select>
          </div>
          {errors.root && <p role="alert" className="text-sm text-destructive">{errors.root.message}</p>}
          <Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving..." : "Register patient"}</Button>
        </form>
      </Card>
    </>
  );
}

export function PatientDetailPage() {
  const { id = "" } = useParams();
  const patient = usePatient(id);
  const history = usePatientScreenings(id);

  if (patient.isPending) return <ListSkeleton />;
  if (patient.isError) return <ErrorState error={patient.error} onRetry={() => void patient.refetch()} />;
  const p = patient.data;

  return (
    <>
      <PageHeader title={p.code}
        description={[p.year_of_birth && `born ${p.year_of_birth}`, p.sex !== "unknown" && p.sex,
          p.has_diabetes === true ? "diabetic" : p.has_diabetes === false ? "not diabetic" : null].filter(Boolean).join(" · ") || "No details recorded"}
        action={<Link to={`/screen?patient=${p.id}`} className={buttonVariants({ size: "sm" })}><Camera aria-hidden className="h-4 w-4" />Screen</Link>} />
      <h2 className="mb-2 font-semibold">Screening history</h2>
      {history.isPending && <ListSkeleton />}
      {history.isError && <ErrorState error={history.error} onRetry={() => void history.refetch()} />}
      {history.isSuccess && history.data.length === 0 && <EmptyState title="No screenings yet" />}
      <div className="flex flex-col gap-2">
        {history.data?.map((s) => <ScreeningListItem key={s.id} screening={s} showPatient={false} />)}
      </div>
    </>
  );
}
