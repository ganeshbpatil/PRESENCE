"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
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
import {
  Button,
  Card,
  ConfirmButton,
  EmptyState,
  ErrorState,
  StatusBadge,
  TextInput,
} from "@/components/ui";

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
    return <main className="flex-1 p-6 text-sm text-neutral-500">Loading...</main>;
  }
  if (error) {
    return (
      <main className="flex-1 p-6 max-w-3xl mx-auto w-full">
        <ErrorState message={error} />
      </main>
    );
  }
  if (!data || !token) return null;

  const { agency, businesses, users } = data;

  return (
    <main className="flex-1 p-6 max-w-3xl mx-auto w-full space-y-6">
      <div>
        <h1 className="text-lg font-semibold">{agency.name}</h1>
        {agency.is_white_label && <StatusBadge status="healthy" />}
      </div>

      {canWrite && <AgencyEditForm token={token} agency={agency} onSaved={reload} />}

      <Card title="Businesses">
        {businesses.length === 0 ? (
          <EmptyState label="No businesses under this agency yet." />
        ) : (
          <ul className="divide-y divide-neutral-100 dark:divide-neutral-900">
            {businesses.map((b) => (
              <li key={b.id}>
                <Link
                  href={`/businesses/${b.id}`}
                  className="flex items-center justify-between py-2 text-sm hover:underline"
                >
                  <span>{b.name}</span>
                  {b.subscription_status && <StatusBadge status={b.subscription_status} />}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <TeamCard token={token} users={users} canWrite={canWrite} onChanged={reload} />
    </main>
  );
}

function AgencyEditForm({
  token,
  agency,
  onSaved,
}: {
  token: string;
  agency: AgencyResponse;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(agency.name);
  const [revenueSharePct, setRevenueSharePct] = useState(agency.revenue_share_pct ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="text-sm underline text-left">
        Edit agency details
      </button>
    );
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await updateAgency(token, agency.id, {
        name,
        revenue_share_pct: revenueSharePct || undefined,
      });
      setOpen(false);
      onSaved();
    } catch {
      setError("Could not save changes.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Edit agency">
      <div className="space-y-2">
        <TextInput value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
        <TextInput
          value={revenueSharePct}
          onChange={(e) => setRevenueSharePct(e.target.value)}
          placeholder="Revenue share %"
          inputMode="decimal"
        />
        {error && <ErrorState message={error} />}
        <div className="flex gap-2">
          <Button onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
          <Button variant="secondary" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
      </div>
    </Card>
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
    <Card title="Team">
      {users.length === 0 ? (
        <EmptyState label="No users on this agency yet." />
      ) : (
        <ul className="space-y-2">
          {users.map((u) => (
            <li key={u.id} className="flex items-center justify-between text-sm">
              <span>
                {u.email} <span className="text-neutral-500">({u.role})</span>
              </span>
              <div className="flex items-center gap-2">
                <StatusBadge status={u.is_active ? "healthy" : "broken"} />
                {canWrite && (
                  <ConfirmButton
                    variant="secondary"
                    confirmMessage={`${u.is_active ? "Deactivate" : "Reactivate"} ${u.email}?`}
                    onConfirm={() => toggleActive(u)}
                    disabled={busyId === u.id}
                  >
                    {u.is_active ? "Deactivate" : "Reactivate"}
                  </ConfirmButton>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {error && <ErrorState message={error} />}
    </Card>
  );
}
