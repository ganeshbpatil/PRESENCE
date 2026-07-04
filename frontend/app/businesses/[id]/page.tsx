"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  ApiError,
  createCampaign,
  createConnection,
  createContact,
  createReview,
  createScheduledPost,
  draftReviewResponse,
  getAttributionSummary,
  getBusiness,
  getBusinessUsers,
  getConnectionsHealth,
  getContacts,
  getCreditBalances,
  getOAuthStatus,
  getReviews,
  getScheduledPosts,
  rechargeCredit,
  sendReviewResponse,
  triggerComputeCorrelation,
  updateBusiness,
  updateUser,
  type AttributionSummary,
  type BalanceResponse,
  type BusinessResponse,
  type ConnectionResponse,
  type ContactResponse,
  type OAuthStatusResponse,
  type ReviewResponse,
  type ScheduledPostResponse,
  type UserSummary,
} from "@/lib/api";
import {
  Button,
  Card,
  ConfirmButton,
  EmptyState,
  ErrorState,
  Select,
  StatusBadge,
  TextInput,
} from "@/components/ui";

interface PanelData {
  business: BusinessResponse;
  connections: ConnectionResponse[];
  reviews: ReviewResponse[];
  posts: ScheduledPostResponse[];
  balances: BalanceResponse[];
  contacts: ContactResponse[];
  oauthStatus: OAuthStatusResponse | null;
  attribution: AttributionSummary | null;
  team: UserSummary[];
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

  const canWrite = user?.role !== "agency_viewer";

  const load = useCallback(
    async (authToken: string) => {
      try {
        const [business, connections, reviews, posts, balances, contacts, oauthStatus, team] =
          await Promise.all([
            getBusiness(authToken, id),
            getConnectionsHealth(authToken, id),
            getReviews(authToken, id),
            getScheduledPosts(authToken, id),
            getCreditBalances(authToken, id),
            getContacts(authToken, id),
            getOAuthStatus(authToken),
            getBusinessUsers(authToken, id),
          ]);
        let attribution: AttributionSummary | null = null;
        try {
          attribution = await getAttributionSummary(authToken, id);
        } catch {
          attribution = null; // none computed yet -- not an error
        }
        setData({
          business,
          connections,
          reviews,
          posts,
          balances,
          contacts,
          oauthStatus,
          attribution,
          team,
        });
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          setError("You don't have access to this business.");
        } else if (err instanceof ApiError && err.status === 404) {
          setError("Business not found.");
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

  const { business, connections, reviews, posts, balances, contacts, oauthStatus, attribution, team } =
    data;

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

      {canWrite && (
        <BusinessEditForm token={token} business={business} onSaved={reload} />
      )}

      <ConnectionsCard
        token={token}
        businessId={id}
        connections={connections}
        oauthStatus={oauthStatus}
        canWrite={canWrite}
        onChanged={reload}
      />

      <CreditCard token={token} businessId={id} balances={balances} canWrite={canWrite} onChanged={reload} />

      <ReviewsCard token={token} businessId={id} reviews={reviews} canWrite={canWrite} onChanged={reload} />

      <PostsCard token={token} businessId={id} posts={posts} canWrite={canWrite} onChanged={reload} />

      <TeamCard token={token} team={team} canWrite={canWrite} onChanged={reload} />

      <ContactsCard
        token={token}
        businessId={id}
        contacts={contacts}
        canWrite={canWrite}
        onChanged={reload}
      />

      {canWrite && (
        <CampaignCard token={token} businessId={id} contacts={contacts} onChanged={reload} />
      )}

      <AttributionCard
        token={token}
        businessId={id}
        summary={attribution}
        canWrite={canWrite}
        onChanged={reload}
      />
    </main>
  );
}

function BusinessEditForm({
  token,
  business,
  onSaved,
}: {
  token: string;
  business: BusinessResponse;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(business.name);
  const [pincode, setPincode] = useState(business.pincode ?? "");
  const [area, setArea] = useState(business.area ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="text-sm underline text-left">
        Edit business details
      </button>
    );
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await updateBusiness(token, business.id, { name, pincode, area });
      setOpen(false);
      onSaved();
    } catch {
      setError("Could not save changes.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Edit business">
      <div className="space-y-2">
        <TextInput value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
        <TextInput
          value={area}
          onChange={(e) => setArea(e.target.value)}
          placeholder="Area"
        />
        <TextInput
          value={pincode}
          onChange={(e) => setPincode(e.target.value)}
          placeholder="Pincode"
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

function ConnectionsCard({
  token,
  businessId,
  connections,
  oauthStatus,
  canWrite,
  onChanged,
}: {
  token: string;
  businessId: string;
  connections: ConnectionResponse[];
  oauthStatus: OAuthStatusResponse | null;
  canWrite: boolean;
  onChanged: () => void;
}) {
  const [platform, setPlatform] = useState<"gbp" | "meta" | "whatsapp">("gbp");
  const [externalId, setExternalId] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    setError(null);
    try {
      await createConnection(token, businessId, {
        platform,
        external_id: externalId || undefined,
        access_token: accessToken || undefined,
      });
      setExternalId("");
      setAccessToken("");
      onChanged();
    } catch {
      setError("Could not create connection.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Platform connections">
      {connections.length === 0 ? (
        <EmptyState label="No platform connections yet." />
      ) : (
        <ul className="space-y-2 mb-3">
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

      {canWrite && (
        <div className="space-y-2 pt-3 border-t border-neutral-100 dark:border-neutral-900">
          <div className="flex gap-2">
            <Select value={platform} onChange={(e) => setPlatform(e.target.value as typeof platform)}>
              <option value="gbp">GBP</option>
              <option value="meta">Meta</option>
              <option value="whatsapp">WhatsApp</option>
            </Select>
            <TextInput
              value={externalId}
              onChange={(e) => setExternalId(e.target.value)}
              placeholder="External ID (e.g. locations/123)"
            />
          </div>
          <TextInput
            value={accessToken}
            onChange={(e) => setAccessToken(e.target.value)}
            placeholder="Access token (manual, until OAuth is wired up)"
            type="password"
          />
          {error && <ErrorState message={error} />}
          <Button onClick={submit} disabled={saving}>
            {saving ? "Adding..." : "Add connection"}
          </Button>

          <div className="flex gap-2 pt-2">
            <Button
              variant="secondary"
              disabled
              title={
                oauthStatus?.gbp_configured
                  ? "GBP OAuth is configured but the redirect flow isn't wired up yet"
                  : "Set GBP_CLIENT_ID/SECRET to enable"
              }
            >
              Connect GBP via OAuth
            </Button>
            <Button
              variant="secondary"
              disabled
              title={
                oauthStatus?.meta_configured
                  ? "Meta OAuth is configured but the redirect flow isn't wired up yet"
                  : "Set META_APP_ID/SECRET to enable"
              }
            >
              Connect Meta via OAuth
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

function CreditCard({
  token,
  businessId,
  balances,
  canWrite,
  onChanged,
}: {
  token: string;
  businessId: string;
  balances: BalanceResponse[];
  canWrite: boolean;
  onChanged: () => void;
}) {
  const [creditType, setCreditType] = useState<"ai" | "whatsapp">("ai");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!amount) return;
    setSaving(true);
    setError(null);
    try {
      await rechargeCredit(token, businessId, { credit_type: creditType, amount });
      setAmount("");
      onChanged();
    } catch {
      setError("Could not recharge credit.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Credit balances">
      {balances.length === 0 ? (
        <EmptyState label="No credit activity yet." />
      ) : (
        <ul className="space-y-2 mb-3">
          {balances.map((b) => (
            <li key={b.credit_type} className="flex items-center justify-between text-sm">
              <span className="capitalize">{b.credit_type}</span>
              <span className="font-mono">{b.balance}</span>
            </li>
          ))}
        </ul>
      )}

      {canWrite && (
        <div className="flex gap-2 pt-3 border-t border-neutral-100 dark:border-neutral-900">
          <Select
            value={creditType}
            onChange={(e) => setCreditType(e.target.value as typeof creditType)}
          >
            <option value="ai">AI</option>
            <option value="whatsapp">WhatsApp</option>
          </Select>
          <TextInput
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Amount"
            inputMode="decimal"
          />
          <ConfirmButton
            confirmMessage={`Recharge ${amount || "0"} ${creditType} credit for this business?`}
            onConfirm={submit}
            disabled={saving || !amount}
          >
            {saving ? "Recharging..." : "Recharge"}
          </ConfirmButton>
        </div>
      )}
      {error && <ErrorState message={error} />}
    </Card>
  );
}

function ReviewsCard({
  token,
  businessId,
  reviews,
  canWrite,
  onChanged,
}: {
  token: string;
  businessId: string;
  reviews: ReviewResponse[];
  canWrite: boolean;
  onChanged: () => void;
}) {
  const [rating, setRating] = useState("5");
  const [text, setText] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function addTestReview() {
    setError(null);
    try {
      await createReview(token, businessId, {
        platform: "gbp",
        rating: Number(rating),
        text: text || undefined,
      });
      setText("");
      onChanged();
    } catch {
      setError("Could not add review.");
    }
  }

  async function draft(reviewId: string) {
    setBusyId(reviewId);
    setError(null);
    try {
      await draftReviewResponse(token, reviewId);
      onChanged();
    } catch {
      setError("Could not draft a response (check AI credit balance).");
    } finally {
      setBusyId(null);
    }
  }

  async function send(reviewId: string) {
    setBusyId(reviewId);
    setError(null);
    try {
      await sendReviewResponse(token, reviewId);
      onChanged();
    } catch {
      setError("Could not send response.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card title="Reviews">
      {reviews.length === 0 ? (
        <EmptyState label="No reviews synced yet." />
      ) : (
        <ul className="space-y-3 mb-3">
          {reviews.map((r) => (
            <li
              key={r.id}
              className="text-sm border-b border-neutral-100 dark:border-neutral-900 pb-3 last:border-0 last:pb-0"
            >
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
              {canWrite && !r.response_sent_at && (
                <div className="flex gap-2 mt-2">
                  {!r.ai_drafted_response && (
                    <Button
                      variant="secondary"
                      onClick={() => draft(r.id)}
                      disabled={busyId === r.id}
                    >
                      Draft response (1 AI credit)
                    </Button>
                  )}
                  {r.ai_drafted_response && (
                    <ConfirmButton
                      confirmMessage="Send this drafted response? This is a public-facing action."
                      onConfirm={() => send(r.id)}
                      disabled={busyId === r.id}
                    >
                      Send response
                    </ConfirmButton>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {canWrite && (
        <div className="space-y-2 pt-3 border-t border-neutral-100 dark:border-neutral-900">
          <p className="text-xs text-neutral-500">
            Add a test review (dev-only stand-in for a real GBP/Meta sync).
          </p>
          <div className="flex gap-2">
            <Select value={rating} onChange={(e) => setRating(e.target.value)}>
              {[5, 4, 3, 2, 1].map((n) => (
                <option key={n} value={n}>
                  {n} star
                </option>
              ))}
            </Select>
            <TextInput
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Review text"
            />
          </div>
          <Button onClick={addTestReview}>Add test review</Button>
        </div>
      )}
      {error && <ErrorState message={error} />}
    </Card>
  );
}

function PostsCard({
  token,
  businessId,
  posts,
  canWrite,
  onChanged,
}: {
  token: string;
  businessId: string;
  posts: ScheduledPostResponse[];
  canWrite: boolean;
  onChanged: () => void;
}) {
  const [platform, setPlatform] = useState("meta");
  const [content, setContent] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!content || !scheduledAt) return;
    setSaving(true);
    setError(null);
    try {
      await createScheduledPost(token, businessId, {
        platform,
        content,
        scheduled_at: new Date(scheduledAt).toISOString(),
      });
      setContent("");
      setScheduledAt("");
      onChanged();
    } catch {
      setError("Could not schedule post.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Scheduled social posts">
      {posts.length === 0 ? (
        <EmptyState label="No posts scheduled." />
      ) : (
        <ul className="space-y-2 mb-3">
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

      {canWrite && (
        <div className="space-y-2 pt-3 border-t border-neutral-100 dark:border-neutral-900">
          <div className="flex gap-2">
            <Select value={platform} onChange={(e) => setPlatform(e.target.value)}>
              <option value="meta">Meta</option>
              <option value="instagram">Instagram</option>
            </Select>
            <input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              className="rounded border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-1.5 text-sm"
            />
          </div>
          <TextInput
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Post content"
          />
          {error && <ErrorState message={error} />}
          <Button onClick={submit} disabled={saving}>
            {saving ? "Scheduling..." : "Schedule post"}
          </Button>
        </div>
      )}
    </Card>
  );
}

function ContactsCard({
  token,
  businessId,
  contacts,
  canWrite,
  onChanged,
}: {
  token: string;
  businessId: string;
  contacts: ContactResponse[];
  canWrite: boolean;
  onChanged: () => void;
}) {
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!phone) return;
    setSaving(true);
    setError(null);
    try {
      await createContact(token, { business_id: businessId, phone_e164: phone, opt_in: true });
      setPhone("");
      onChanged();
    } catch {
      setError("Could not add contact.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="WhatsApp contacts">
      {contacts.length === 0 ? (
        <EmptyState label="No contacts yet." />
      ) : (
        <ul className="space-y-1 mb-3">
          {contacts.map((c) => (
            <li key={c.id} className="flex items-center justify-between text-sm">
              <span className="font-mono">{c.phone_e164}</span>
              <StatusBadge status={c.opt_in ? "healthy" : "broken"} />
            </li>
          ))}
        </ul>
      )}

      {canWrite && (
        <div className="flex gap-2 pt-3 border-t border-neutral-100 dark:border-neutral-900">
          <TextInput
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+91XXXXXXXXXX"
          />
          <Button onClick={submit} disabled={saving}>
            {saving ? "Adding..." : "Add contact"}
          </Button>
        </div>
      )}
      {error && <ErrorState message={error} />}
    </Card>
  );
}

function CampaignCard({
  token,
  businessId,
  contacts,
  onChanged,
}: {
  token: string;
  businessId: string;
  contacts: ContactResponse[];
  onChanged: () => void;
}) {
  const [name, setName] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [category, setCategory] = useState<"marketing" | "utility" | "authentication">(
    "utility"
  );
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const optedInCount = contacts.filter((c) => c.opt_in).length;

  async function submit() {
    if (!name || !templateName) return;
    setSending(true);
    setError(null);
    setResult(null);
    try {
      const summary = await createCampaign(token, {
        business_id: businessId,
        name,
        template_name: templateName,
        category,
      });
      setResult(
        `Sent ${summary.sent}, failed ${summary.failed}, skipped (insufficient credit) ${summary.skipped_insufficient_credit}`
      );
      setName("");
      setTemplateName("");
      onChanged();
    } catch {
      setError("Could not send campaign.");
    } finally {
      setSending(false);
    }
  }

  return (
    <Card title="WhatsApp campaigns">
      <p className="text-xs text-neutral-500 mb-2">
        Sends to all {optedInCount} opted-in contact(s) — real messages, real credit.
      </p>
      <div className="space-y-2">
        <TextInput
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Campaign name"
        />
        <TextInput
          value={templateName}
          onChange={(e) => setTemplateName(e.target.value)}
          placeholder="Template name (must exist in Gallabox)"
        />
        <Select value={category} onChange={(e) => setCategory(e.target.value as typeof category)}>
          <option value="utility">Utility</option>
          <option value="marketing">Marketing</option>
          <option value="authentication">Authentication</option>
        </Select>
        {error && <ErrorState message={error} />}
        {result && <p className="text-sm text-neutral-600 dark:text-neutral-400">{result}</p>}
        <ConfirmButton
          confirmMessage={`Send "${name || "this campaign"}" to ${optedInCount} opted-in contact(s) now?`}
          onConfirm={submit}
          disabled={sending || !name || !templateName}
        >
          {sending ? "Sending..." : "Send campaign"}
        </ConfirmButton>
      </div>
    </Card>
  );
}

function AttributionCard({
  token,
  businessId,
  summary,
  canWrite,
  onChanged,
}: {
  token: string;
  businessId: string;
  summary: AttributionSummary | null;
  canWrite: boolean;
  onChanged: () => void;
}) {
  const [queued, setQueued] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function trigger() {
    setError(null);
    try {
      const now = new Date();
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      await triggerComputeCorrelation(token, {
        business_id: businessId,
        period_start: weekAgo.toISOString(),
        period_end: now.toISOString(),
      });
      setQueued(true);
      setTimeout(onChanged, 2000);
    } catch {
      setError("Could not queue attribution computation.");
    }
  }

  return (
    <Card title="Attribution">
      {summary ? (
        <ul className="space-y-1 text-sm">
          <li>
            Correlation score:{" "}
            <span className="font-mono">{summary.correlation_score ?? "—"}</span>
          </li>
          <li>
            Signal completeness:{" "}
            <span className="font-mono">{summary.signal_completeness_pct ?? "—"}%</span>
          </li>
          <li className="text-neutral-500 text-xs">
            Computed {new Date(summary.computed_at).toLocaleString()}
          </li>
        </ul>
      ) : (
        <EmptyState label="No attribution correlation computed yet." />
      )}
      {canWrite && (
        <div className="pt-3 mt-3 border-t border-neutral-100 dark:border-neutral-900">
          {error && <ErrorState message={error} />}
          <Button onClick={trigger} disabled={queued}>
            {queued ? "Queued — recomputing..." : "Recompute (last 7 days)"}
          </Button>
        </div>
      )}
    </Card>
  );
}

function TeamCard({
  token,
  team,
  canWrite,
  onChanged,
}: {
  token: string;
  team: UserSummary[];
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
      {team.length === 0 ? (
        <EmptyState label="No users on this business yet." />
      ) : (
        <ul className="space-y-2">
          {team.map((u) => (
            <li key={u.id} className="flex items-center justify-between text-sm">
              <span>{u.email}</span>
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
