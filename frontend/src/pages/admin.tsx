import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/AppShell";
import { EmptyState, ErrorState, ListSkeleton, describeError } from "@/components/feedback";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Select } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { useAnalytics, useUpdateUser, useUsers } from "@/hooks/queries";
import type { AccountStatus, Role } from "@/lib/api/types";
import { ROLE_LABEL, formatDate, percent } from "@/lib/utils";

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="flex flex-col gap-0.5 p-3">
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
      {hint && <span className="text-[11px] text-muted-foreground">{hint}</span>}
    </Card>
  );
}

const CONDITION_NAME: Record<string, string> = { dr: "Diabetic retinopathy", glaucoma: "Glaucoma", cataract: "Cataract" };

export function AnalyticsPage() {
  const analytics = useAnalytics();
  if (analytics.isPending) return <ListSkeleton rows={4} />;
  if (analytics.isError) return <ErrorState error={analytics.error} onRetry={() => void analytics.refetch()} />;
  const a = analytics.data;
  const perDay = a.screenings_per_day.map((d) => ({ ...d, label: formatDate(`${d.day}T00:00:00`) }));

  return (
    <>
      <PageHeader title="Analytics" description="Aggregate counts only. No images, patient codes or names." />
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatTile label="Screenings" value={String(a.total_screenings)} />
        <StatTile label="Referral rate" value={a.referral_rate === null ? "-" : percent(a.referral_rate)} />
        <StatTile label="Open referrals" value={String(a.open_referrals)} />
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
              {Object.keys(CONDITION_NAME).map((c) => (
                <li key={c} className="flex justify-between">
                  <span>{CONDITION_NAME[c]}</span>
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

  const change = async (id: string, body: { role?: Role; is_active?: boolean; status?: AccountStatus }) => {
    try {
      await update.mutateAsync({ id, ...body });
      toast("User updated.", "success");
    } catch (error) {
      toast(describeError(error), "error");
    }
  };

  return (
    <>
      <PageHeader title="Users"
        description="Approve new health workers after checking their facility and registration number. Assign roles." />
      {users.isPending && <ListSkeleton />}
      {users.isError && <ErrorState error={users.error} onRetry={() => void users.refetch()} />}
      {users.isSuccess && users.data.length === 0 && <EmptyState title="No users" />}
      <div className="flex flex-col gap-2">
        {users.data?.map((u) => {
          const self = u.id === me?.id;
          return (
            <Card key={u.id} className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center">
              <div className="flex-1">
                <p className="text-sm font-medium">{u.full_name} {self && <Badge tone="info">You</Badge>} {!u.is_active && <Badge tone="high">Deactivated</Badge>}
                  {u.status === "pending" && <Badge tone="medium">Waiting for approval</Badge>} {u.status === "rejected" && <Badge tone="high">Rejected</Badge>}</p>
                <p className="text-xs text-muted-foreground">{u.email} · joined {formatDate(u.created_at)}</p>
                {(u.facility || u.registration_number) && (
                  <p className="text-xs text-muted-foreground">{u.facility ?? "facility not given"} · registration no. {u.registration_number ?? "not given"}</p>
                )}
              </div>
              {u.status === "pending" && !self && (
                <div className="flex gap-2">
                  <Button size="sm" disabled={update.isPending} onClick={() => void change(u.id, { status: "approved" })}>Approve</Button>
                  <Button size="sm" variant="outline" disabled={update.isPending} onClick={() => void change(u.id, { status: "rejected" })}>Reject</Button>
                </div>
              )}
              <div className="flex gap-2">
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
