"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Building2, Pencil, Users } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import {
  ApiError,
  getAgency,
  getAgencyBusinesses,
  getAgencyUsers,
  updateAgency,
  updateUser,
  type AgencyResponse,
  type BusinessSummary,
  type UserSummary,
} from "@/lib/api";
import { EmptyState, ErrorState, StatusBadge } from "@/components/ui";
import { AppShell } from "@/components/shell/app-shell";
import { ConfirmAction } from "@/components/confirm-action";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

interface PanelData {
  agency: AgencyResponse;
  businesses: BusinessSummary[];
  users: UserSummary[];
}

export default function AgencyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { token, user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<PanelData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);

  const canWrite = user?.role === "agency_admin";

  const load = useCallback(
    async (authToken: string) => {
      try {
        const [agency, businesses, users] = await Promise.all([
          getAgency(authToken, id),
          getAgencyBusinesses(authToken, id),
          getAgencyUsers(authToken, id),
        ]);
        setData({ agency, businesses, users });
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          setError("You don't have access to this agency.");
        } else if (err instanceof ApiError && err.status === 404) {
          setError("Agency not found.");
        } else {
          setError("Could not reach PRESENCE — is the API up?");
        }
      }
    },
    [id]
  );

  useEffect(() => {
    if (authLoading) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    (async () => {
      await load(token);
    })();
  }, [authLoading, token, router, load]);

  const reload = () => token && load(token);

  if (authLoading || (!data && !error)) {
    return <main className="flex-1 p-6 text-sm text-muted-foreground">Loading...</main>;
  }
  if (error) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 p-6">
        <ErrorState message={error} />
      </main>
    );
  }
  if (!data || !token) return null;

  const { agency, businesses, users } = data;

  return (
    <AppShell title={agency.name} subtitle="Agency">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {agency.is_white_label && <StatusBadge status="healthy" />}
              Agency details
            </CardTitle>
            {canWrite && (
              <CardAction>
                <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                  <Pencil />
                  Edit
                </Button>
              </CardAction>
            )}
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Revenue share: {agency.revenue_share_pct ?? "—"}%
          </CardContent>
        </Card>

        {canWrite && (
          <AgencyEditDialog
            token={token}
            agency={agency}
            open={editOpen}
            onOpenChange={setEditOpen}
            onSaved={reload}
          />
        )}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="size-4 text-muted-foreground" />
              Businesses
            </CardTitle>
          </CardHeader>
          <CardContent>
            {businesses.length === 0 ? (
              <EmptyState label="No businesses under this agency yet." icon={Building2} />
            ) : (
              <ul className="divide-y">
                {businesses.map((b) => (
                  <li key={b.id}>
                    <Link
                      href={`/businesses/${b.id}`}
                      className="flex items-center justify-between py-2 text-sm transition-colors hover:text-foreground"
                    >
                      <span>{b.name}</span>
                      {b.subscription_status && <StatusBadge status={b.subscription_status} />}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <TeamCard token={token} users={users} canWrite={canWrite} onChanged={reload} />
      </div>
    </AppShell>
  );
}

function AgencyEditDialog({
  token,
  agency,
  open,
  onOpenChange,
  onSaved,
}: {
  token: string;
  agency: AgencyResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(agency.name);
  const [revenueSharePct, setRevenueSharePct] = useState(agency.revenue_share_pct ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await updateAgency(token, agency.id, {
        name,
        revenue_share_pct: revenueSharePct || undefined,
      });
      onOpenChange(false);
      onSaved();
    } catch {
      setError("Could not save changes.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setName(agency.name);
          setRevenueSharePct(agency.revenue_share_pct ?? "");
          setError(null);
        }
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Pencil className="size-4 text-muted-foreground" />
            Edit agency
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
          <Input
            value={revenueSharePct}
            onChange={(e) => setRevenueSharePct(e.target.value)}
            placeholder="Revenue share %"
            inputMode="decimal"
          />
          {error && <ErrorState message={error} />}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function TeamCard({
  token,
  users,
  canWrite,
  onChanged,
}: {
  token: string;
  users: UserSummary[];
  canWrite: boolean;
  onChanged: () => void;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function toggleActive(u: UserSummary) {
    setBusyId(u.id);
    setError(null);
    try {
      await updateUser(token, u.id, { is_active: !u.is_active });
      onChanged();
    } catch {
      setError("Could not update that user (you can't deactivate yourself).");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="size-4 text-muted-foreground" />
          Team
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {users.length === 0 ? (
          <EmptyState label="No users on this agency yet." icon={Users} />
        ) : (
          <ul className="space-y-2">
            {users.map((u) => (
              <li key={u.id} className="flex items-center justify-between text-sm">
                <span>
                  {u.email} <span className="text-muted-foreground">({u.role})</span>
                </span>
                <div className="flex items-center gap-2">
                  <StatusBadge status={u.is_active ? "healthy" : "broken"} />
                  {canWrite && (
                    <ConfirmAction
                      variant="outline"
                      title={u.is_active ? "Deactivate user" : "Reactivate user"}
                      description={`${u.is_active ? "Deactivate" : "Reactivate"} ${u.email}?`}
                      onConfirm={() => toggleActive(u)}
                      disabled={busyId === u.id}
                    >
                      {u.is_active ? "Deactivate" : "Reactivate"}
                    </ConfirmAction>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
        {error && <ErrorState message={error} />}
      </CardContent>
    </Card>
  );
}
