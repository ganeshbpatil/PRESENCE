"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { getAgencyBusinesses, ApiError, type BusinessSummary } from "@/lib/api";
import { EmptyState, ErrorState, StatusBadge } from "@/components/ui";

export default function HomePage() {
  const { token, user, loading, logout } = useAuth();
  const router = useRouter();
  const [businesses, setBusinesses] = useState<BusinessSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (user.role === "smb_owner" && user.business_id) {
      router.replace(`/businesses/${user.business_id}`);
      return;
    }
    if (user.agency_id && token) {
      getAgencyBusinesses(token, user.agency_id)
        .then(setBusinesses)
        .catch((err) =>
          setError(err instanceof ApiError ? err.message : "Could not load businesses.")
        );
    }
  }, [loading, user, token, router]);

  if (loading || (!error && !businesses && user?.agency_id)) {
    return <main className="flex-1 p-6 text-sm text-neutral-500">Loading...</main>;
  }
  if (!user) return null; // redirecting to /login

  return (
    <main className="flex-1 p-6 max-w-3xl mx-auto w-full space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Agency businesses</h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400">{user.email}</p>
        </div>
        <div className="flex items-center gap-3">
          {user.agency_id && (
            <Link href={`/agencies/${user.agency_id}`} className="text-sm underline">
              Manage agency
            </Link>
          )}
          <Link href="/businesses/new" className="text-sm underline">
            Add business
          </Link>
          <button onClick={logout} className="text-sm underline">
            Sign out
          </button>
        </div>
      </div>

      {error && <ErrorState message={error} />}
      {businesses && businesses.length === 0 && (
        <EmptyState label="No businesses under this agency yet." />
      )}
      {businesses && businesses.length > 0 && (
        <ul className="divide-y divide-neutral-200 dark:divide-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-800">
          {businesses.map((b) => (
            <li key={b.id}>
              <Link
                href={`/businesses/${b.id}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-neutral-50 dark:hover:bg-neutral-900"
              >
                <div>
                  <p className="font-medium">{b.name}</p>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400">
                    {b.category} &middot; {b.tier}
                  </p>
                </div>
                {b.subscription_status && <StatusBadge status={b.subscription_status} />}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
