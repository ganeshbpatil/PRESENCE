"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  ApiError,
  getBusiness,
  getConnectionsHealth,
  getCreditBalances,
  getReviews,
  getScheduledPosts,
  type BalanceResponse,
  type BusinessResponse,
  type ConnectionResponse,
  type ReviewResponse,
  type ScheduledPostResponse,
} from "@/lib/api";
import { Card, EmptyState, ErrorState, StatusBadge } from "@/components/ui";

interface PanelData {
  business: BusinessResponse;
  connections: ConnectionResponse[];
  reviews: ReviewResponse[];
  posts: ScheduledPostResponse[];
  balances: BalanceResponse[];
}

export default function BusinessDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { token, user, loading: authLoading, logout } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<PanelData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    Promise.all([
      getBusiness(token, id),
      getConnectionsHealth(token, id),
      getReviews(token, id),
      getScheduledPosts(token, id),
      getCreditBalances(token, id),
    ])
      .then(([business, connections, reviews, posts, balances]) =>
        setData({ business, connections, reviews, posts, balances })
      )
      .catch((err) => {
        if (err instanceof ApiError && err.status === 403) {
          setError("You don't have access to this business.");
        } else if (err instanceof ApiError && err.status === 404) {
          setError("Business not found.");
        } else {
          setError("Could not reach PRESENCE — is the API up?");
        }
      });
  }, [authLoading, token, id, router]);

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
  if (!data) return null;

  const { business, connections, reviews, posts, balances } = data;

  return (
    <main className="flex-1 p-6 max-w-3xl mx-auto w-full space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold">{business.name}</h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            {business.category} &middot; {business.tier}
            {business.area ? ` · ${business.area}` : ""}
          </p>
        </div>
        <div className="text-right space-y-1">
          {business.subscription_status && (
            <StatusBadge status={business.subscription_status} />
          )}
          {user?.role !== "smb_owner" && (
            <button onClick={logout} className="block text-sm underline">
              Sign out
            </button>
          )}
        </div>
      </div>

      <Card title="Platform connections">
        {connections.length === 0 ? (
          <EmptyState label="No platform connections yet." />
        ) : (
          <ul className="space-y-2">
            {connections.map((c) => (
              <li key={c.id} className="flex items-center justify-between text-sm">
                <span className="capitalize">
                  {c.platform}
                  {c.provider ? ` (${c.provider})` : ""}
                </span>
                <StatusBadge status={c.sync_status} />
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Credit balances">
        {balances.length === 0 ? (
          <EmptyState label="No credit activity yet." />
        ) : (
          <ul className="space-y-2">
            {balances.map((b) => (
              <li key={b.credit_type} className="flex items-center justify-between text-sm">
                <span className="capitalize">{b.credit_type}</span>
                <span className="font-mono">{b.balance}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Reviews">
        {reviews.length === 0 ? (
          <EmptyState label="No reviews synced yet." />
        ) : (
          <ul className="space-y-3">
            {reviews.map((r) => (
              <li key={r.id} className="text-sm border-b border-neutral-100 dark:border-neutral-900 pb-3 last:border-0 last:pb-0">
                <div className="flex items-center justify-between">
                  <span className="capitalize font-medium">
                    {r.platform} {r.rating ? `★ ${r.rating}` : ""}
                  </span>
                  <StatusBadge status={r.response_sent_at ? "posted" : "pending"} />
                </div>
                {r.text && (
                  <p className="text-neutral-600 dark:text-neutral-400 mt-1">{r.text}</p>
                )}
                {r.ai_drafted_response && (
                  <p className="text-neutral-500 dark:text-neutral-500 mt-1 italic">
                    Draft: {r.ai_drafted_response}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Scheduled social posts">
        {posts.length === 0 ? (
          <EmptyState label="No posts scheduled." />
        ) : (
          <ul className="space-y-2">
            {posts.map((p) => (
              <li key={p.id} className="flex items-center justify-between text-sm">
                <span>
                  {p.platform} &middot; {new Date(p.scheduled_at).toLocaleString()}
                </span>
                <StatusBadge status={p.status} />
              </li>
            ))}
          </ul>
        )}
      </Card>
    </main>
  );
}
