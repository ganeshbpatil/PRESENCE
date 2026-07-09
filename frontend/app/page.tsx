"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, CheckCircle2, Clock, MessageSquareText, Star } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { getAgencyDashboard, ApiError, type AgencyDashboard } from "@/lib/api";
import { ErrorState } from "@/components/ui";
import { AppShell } from "@/components/shell/app-shell";
import { StatCard } from "@/components/stat-card";
import { ReviewVolumeChart, RatingDistributionChart } from "@/components/dashboard-charts";

export default function DashboardPage() {
  const { token, user, loading } = useAuth();
  const router = useRouter();
  const [dashboard, setDashboard] = useState<AgencyDashboard | null>(null);
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
      getAgencyDashboard(token, user.agency_id)
        .then(setDashboard)
        .catch((err) =>
          setError(err instanceof ApiError ? err.message : "Could not load the dashboard.")
        );
    }
  }, [loading, user, token, router]);

  if (loading || (!error && !dashboard && user?.agency_id)) {
    return <main className="flex-1 p-6 text-sm text-muted-foreground">Loading...</main>;
  }
  if (!user) return null; // redirecting to /login

  return (
    <AppShell title="Dashboard" subtitle={user.email}>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
        {error && <ErrorState message={error} />}

        {dashboard && (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <StatCard
                icon={Building2}
                label="Active businesses"
                value={`${dashboard.active_businesses} / ${dashboard.total_businesses}`}
              />
              <StatCard
                icon={Star}
                label="Avg rating"
                value={dashboard.avg_rating != null ? dashboard.avg_rating.toFixed(1) : "—"}
              />
              <StatCard
                icon={MessageSquareText}
                label="Reviews this month"
                value={dashboard.reviews_this_month}
              />
              <StatCard icon={Clock} label="Pending replies" value={dashboard.pending_replies} />
              <StatCard
                icon={CheckCircle2}
                label="Reply rate"
                value={
                  dashboard.reply_rate_pct != null
                    ? `${dashboard.reply_rate_pct.toFixed(0)}%`
                    : "—"
                }
              />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <ReviewVolumeChart data={dashboard.review_volume} />
              <RatingDistributionChart data={dashboard.rating_distribution} />
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
