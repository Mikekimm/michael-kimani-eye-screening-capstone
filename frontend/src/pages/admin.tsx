import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/AppShell";
import { EmptyState, ErrorState, ListSkeleton, describeError } from "@/components/feedback";
import {
  Badge, Button, Card, CardContent, CardHeader, CardTitle, FieldError, Input, Label, Select, Textarea, buttonVariants,
} from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useAnalytics, useCreateUser, useUpdateUser, useUsers } from "@/hooks/queries";
import type { AccountStatus, Role, User } from "@/lib/api/types";
import { CONDITION_LABEL, ROLE_LABEL, formatDate, percent } from "@/lib/utils";

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="flex flex-col gap-0.5 p-3">
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
      {hint && <span className="text-[11px] text-muted-foreground">{hint}</span>}
    </Card>
  );
}


function PendingApprovalsNotice() {
  const users = useUsers();
  const pending = users.data?.filter((u) => u.status === "pending").length ?? 0;
  if (!pending) return null;
  return (
    <Card role="status" className="mb-4 flex items-center justify-between gap-3 border-risk-medium p-3 text-sm">
      <span>{pending === 1 ? "1 account is" : `${pending} accounts are`} waiting for approval.</span>
      <Link to="/admin/users" className={buttonVariants({ size: "sm" })}>Review</Link>
    </Card>
  );
}

export function AnalyticsPage() {
  const analytics = useAnalytics();
  if (analytics.isPending) return <ListSkeleton rows={4} />;
  if (analytics.isError) return <ErrorState error={analytics.error} onRetry={() => void analytics.refetch()} />;
  const a = analytics.data;
  const perDay = a.screenings_per_day.map((d) => ({ ...d, label: formatDate(`${d.day}T00:00:00`) }));

  return (
    <>
      <PageHeader title="Analytics" description="Aggregate counts only. No images, patient codes or names." />
      <PendingApprovalsNotice />
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
        <StatTile label="Screenings" value={String(a.total_screenings)} />
        <StatTile label="Referral rate" value={a.referral_rate === null ? "-" : percent(a.referral_rate)} />
        <StatTile label="Open referrals" value={String(a.open_referrals)} />
        <StatTile label="Overdue reviews" value={String(a.overdue_referrals)}
          hint={`targets: urgent ${a.review_targets_hours.urgent} h, routine ${a.review_targets_hours.routine} h`} />
        <StatTile label="Median time to review" value={a.median_review_turnaround_hours === null ? "-" : `${a.median_review_turnaround_hours} h`} />
      </div>

      <Card className="mb-4">
        <CardHeader><CardTitle>Screenings per day</CardTitle></CardHeader>
        <CardContent>
          {perDay.length === 0 ? (
            <p className="text-sm text-muted-foreground">No screenings recorded yet.</p>
          ) : (
            <>
              <div className="h-56" role="img" aria-label={`Bar chart of screenings per day over ${perDay.length} days; table below`}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={perDay} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                    <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
                    <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={11} stroke="hsl(var(--muted-foreground))" />
                    <YAxis allowDecimals={false} tickLine={false} axisLine={false} fontSize={11} stroke="hsl(var(--muted-foreground))" />
                    <Tooltip cursor={{ fill: "hsl(var(--muted))" }} formatter={(v: number) => [v, "Screenings"]}
                      contentStyle={{ borderRadius: 8, borderColor: "hsl(var(--border))", fontSize: 12 }} />
                    <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} maxBarSize={28} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <details className="mt-2 text-sm">
                <summary className="cursor-pointer text-muted-foreground">Show as table</summary>
                <table className="mt-2 w-full text-left">
                  <thead><tr><th className="py-1">Day</th><th className="py-1 text-right">Screenings</th></tr></thead>
                  <tbody>{perDay.map((d) => <tr key={d.day} className="border-t"><td className="py-1">{d.label}</td><td className="py-1 text-right tabular-nums">{d.count}</td></tr>)}</tbody>
                </table>
              </details>
            </>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Positive results by condition</CardTitle></CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-1 text-sm">
              {Object.keys(CONDITION_LABEL).map((c) => (
                <li key={c} className="flex justify-between">
                  <span>{CONDITION_LABEL[c]}</span>
                  <span className="tabular-nums">{c in a.positives_per_condition ? a.positives_per_condition[c] : c === "dr" ? 0 : "no model"}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Model versions in use</CardTitle></CardHeader>
          <CardContent>
            {Object.keys(a.model_versions_in_use).length === 0 ? <p className="text-sm text-muted-foreground">None yet.</p> : (
              <ul className="flex flex-col gap-1 text-sm">
                {Object.entries(a.model_versions_in_use).map(([version, count]) => (
                  <li key={version} className="flex justify-between gap-2"><code className="text-xs">{version}</code><span className="tabular-nums">{count} results</span></li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-xs text-muted-foreground">
              Users: {Object.entries(a.users_by_role).map(([r, n]) => `${n} ${ROLE_LABEL[r as Role] ?? r}`).join(", ") || "none"}
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

export function UsersPage() {
  const { user: me } = useAuth();
  const users = useUsers();
  const update = useUpdateUser();
  const toast = useToast();

  const [rejecting, setRejecting] = useState<string | null>(null);

  const change = async (id: string, body: { role?: Role; is_active?: boolean; status?: AccountStatus; status_reason?: string }) => {
    try {
      await update.mutateAsync({ id, ...body });
      toast("User updated.", "success");
      setRejecting(null);
    } catch (error) {
      toast(describeError(error), "error");
    }
  };

  return (
    <>
      <PageHeader title="Users"
        description="A sign-up is a request: it grants nothing until you approve it. Check the person with their facility (for example by phoning it) before approving; the app cannot verify who someone is. You can grant a different role than the one requested." />
      <CreateStaffAccount />
      {users.isPending && <ListSkeleton />}
      {users.isError && <ErrorState error={users.error} onRetry={() => void users.refetch()} />}
      {users.isSuccess && users.data.length === 0 && <EmptyState title="No users" />}
      <div className="flex flex-col gap-2">
        {[...(users.data ?? [])].sort((a, b) => Number(b.status === "pending") - Number(a.status === "pending")).map((u) => {
          const self = u.id === me?.id;
          return (
            <Card key={u.id} className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center">
              <div className="flex-1">
                <p className="text-sm font-medium">{u.full_name} {self && <Badge tone="info">You</Badge>} {!u.is_active && <Badge tone="high">Deactivated</Badge>}
                  {u.status === "pending" && <Badge tone="medium">Waiting for approval</Badge>} {u.status === "rejected" && <Badge tone="high">Rejected</Badge>}</p>
                <p className="text-xs text-muted-foreground">{u.email} · signed up {formatDate(u.created_at)}</p>
                {u.facility && (
                  <p className="text-xs text-muted-foreground">Facility: {u.facility} <span className="italic">(as typed, not verified)</span></p>
                )}
                {u.status === "pending" && u.requested_role && (
                  <p className="text-xs">Requested role: <strong>{ROLE_LABEL[u.requested_role]}</strong> (grants nothing until approved)</p>
                )}
                {u.status === "rejected" && u.status_reason && <p className="text-xs text-risk-high">Rejected: {u.status_reason}</p>}
                {rejecting === u.id && (
                  <RejectForm user={u} busy={update.isPending} onCancel={() => setRejecting(null)}
                    onReject={(reason) => void change(u.id, { status: "rejected", status_reason: reason })} />
                )}
              </div>
              {u.status === "pending" && !self && rejecting !== u.id && (
                <PendingDecision user={u} busy={update.isPending} onApprove={(role) => void change(u.id, { status: "approved", role })}
                  onReject={() => setRejecting(u.id)} />
              )}
              <div className={u.status === "pending" ? "hidden" : "flex gap-2"}>
                <Select aria-label={`Role for ${u.full_name}`} className="w-44" value={u.role} disabled={self || update.isPending}
                  onChange={(e) => void change(u.id, { role: e.target.value as Role })}>
                  {(Object.keys(ROLE_LABEL) as Role[]).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                </Select>
                <Select aria-label={`Status for ${u.full_name}`} className="w-32" value={u.is_active ? "active" : "inactive"} disabled={self || update.isPending}
                  onChange={(e) => void change(u.id, { is_active: e.target.value === "active" })}>
                  <option value="active">Active</option><option value="inactive">Deactivated</option>
                </Select>
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
}

/** Approve with the requested role (or another one the admin picks), or reject with a reason. */
function PendingDecision({ user, busy, onApprove, onReject }: {
  user: User; busy: boolean; onApprove: (role: Role) => void; onReject: () => void;
}) {
  const [role, setRole] = useState<Role>(user.requested_role ?? "health_worker");
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select aria-label={`Role to grant ${user.full_name}`} className="w-40" value={role} onChange={(e) => setRole(e.target.value as Role)}>
        {(Object.keys(ROLE_LABEL) as Role[]).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
      </Select>
      <Button size="sm" disabled={busy} onClick={() => onApprove(role)}>Approve</Button>
      <Button size="sm" variant="outline" disabled={busy} onClick={onReject}>Reject</Button>
    </div>
  );
}

function RejectForm({ user, busy, onReject, onCancel }: {
  user: User; busy: boolean; onReject: (reason: string) => void; onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | undefined>();
  const id = `reject-${user.id}`;
  return (
    <div className="mt-2 flex flex-col gap-1">
      <Label htmlFor={id}>Reason for rejecting (sent to {user.full_name})</Label>
      <Textarea id={id} value={reason} aria-invalid={!!error} aria-describedby={`${id}-error`}
        onChange={(e) => setReason(e.target.value)} placeholder="e.g. Not on the facility's staff list" />
      <FieldError id={`${id}-error`} message={error} />
      <div className="flex gap-2">
        <Button size="sm" variant="outline" disabled={busy}
          onClick={() => (reason.trim() ? onReject(reason.trim()) : setError("Give a reason."))}>Confirm rejection</Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

const staffSchema = z.object({
  full_name: z.string().trim().min(2, "Enter the full name."),
  email: z.string().trim().email("Enter a valid email address."),
  password: z.string().min(8, "Use at least 8 characters.").max(128)
    .refine((v) => /[A-Za-z]/.test(v) && /\d/.test(v), "Use at least one letter and one number."),
  role: z.enum(["health_worker", "specialist", "admin"]),
});

/** Specialists and admins never sign up themselves: an admin creates them here (or promotes an account). */
function CreateStaffAccount() {
  const create = useCreateUser();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const form = useForm<z.infer<typeof staffSchema>>({
    resolver: zodResolver(staffSchema), defaultValues: { full_name: "", email: "", password: "", role: "specialist" },
  });
  const { errors, isSubmitting } = form.formState;
  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await create.mutateAsync(values);
      toast("Account created. Share the temporary password privately; they can change it with Forgot password.", "success");
      form.reset();
      setOpen(false);
    } catch (error) {
      form.setError("root", { message: describeError(error) });
    }
  });
  if (!open) {
    return <Button className="mb-3 w-fit" variant="outline" onClick={() => setOpen(true)}>Create a staff account</Button>;
  }
  const fields = [["full_name", "Full name", "text"], ["email", "Email", "email"], ["password", "Temporary password", "text"]] as const;
  return (
    <Card className="mb-3">
      <CardHeader><CardTitle>New staff account</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="grid gap-3 sm:grid-cols-2">
          {fields.map(([name, label, type]) => (
            <div key={name} className="flex flex-col gap-1">
              <Label htmlFor={`staff-${name}`}>{label}</Label>
              <Input id={`staff-${name}`} type={type} aria-invalid={!!errors[name]} aria-describedby={`staff-${name}-error`} {...form.register(name)} />
              <FieldError id={`staff-${name}-error`} message={errors[name]?.message} />
            </div>
          ))}
          <div className="flex flex-col gap-1">
            <Label htmlFor="staff-role">Role</Label>
            <Select id="staff-role" {...form.register("role")}>
              {(Object.keys(ROLE_LABEL) as Role[]).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
            </Select>
          </div>
          {errors.root && <p role="alert" className="text-sm text-destructive sm:col-span-2">{errors.root.message}</p>}
          <div className="flex gap-2 sm:col-span-2">
            <Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Creating..." : "Create account"}</Button>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
