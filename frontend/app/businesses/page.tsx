"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Building2 } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { getAgencyBusinesses, ApiError, type BusinessSummary } from "@/lib/api";
import { ErrorState, StatusBadge } from "@/components/ui";
import { AppShell } from "@/components/shell/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function BusinessesPage() {
  const { token, user, loading } = useAuth();
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
    return <main className="flex-1 p-6 text-sm text-muted-foreground">Loading...</main>;
  }
  if (!user) return null; // redirecting to /login

  return (
    <AppShell title="Businesses" subtitle={user.email}>
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
        <div className="flex items-center justify-end gap-2">
          {user.agency_id && (
            <Button variant="outline" size="sm" asChild>
              <Link href={`/agencies/${user.agency_id}`}>Manage agency</Link>
            </Button>
          )}
          <Button size="sm" asChild>
            <Link href="/businesses/new">Add business</Link>
          </Button>
        </div>

        {error && <ErrorState message={error} />}

        {businesses && businesses.length === 0 && (
          <Card>
            <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
              <Building2 className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                No businesses under this agency yet.
              </p>
            </CardContent>
          </Card>
        )}

        {businesses && businesses.length > 0 && (
          <Card className="p-0">
            <ul className="divide-y">
              {businesses.map((b) => (
                <li key={b.id}>
                  <Link
                    href={`/businesses/${b.id}`}
                    className="flex items-center justify-between px-4 py-3 transition-colors hover:bg-accent/50"
                  >
                    <div>
                      <p className="font-medium">{b.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {b.category} &middot; {b.tier}
                      </p>
                    </div>
                    {b.subscription_status && <StatusBadge status={b.subscription_status} />}
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
