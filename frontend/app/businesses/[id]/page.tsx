"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  CalendarClock,
  CheckCircle2,
  Clock,
  Link2,
  MessageSquareText,
  MessagesSquare,
  Pencil,
  Send,
  Sparkles,
  Star,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react";
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
  getBusinessDashboard,
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
  type BusinessDashboard,
  type BusinessResponse,
  type ConnectionResponse,
  type ContactResponse,
  type OAuthStatusResponse,
  type ReviewResponse,
  type ScheduledPostResponse,
  type UserSummary,
} from "@/lib/api";
import { EmptyState, ErrorState, StatusBadge } from "@/components/ui";
import { AppShell } from "@/components/shell/app-shell";
import { ConfirmAction } from "@/components/confirm-action";
import { StatCard } from "@/components/stat-card";
import { ReviewVolumeChart, RatingDistributionChart } from "@/components/dashboard-charts";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

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
  dashboard: BusinessDashboard;
}

export default function BusinessDetailPage({
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

  const canWrite = user?.role !== "agency_viewer";

  const load = useCallback(
    async (authToken: string) => {
      try {
        const [
          business,
          connections,
          reviews,
          posts,
          balances,
          contacts,
          oauthStatus,
          team,
          dashboard,
        ] = await Promise.all([
          getBusiness(authToken, id),
          getConnectionsHealth(authToken, id),
          getReviews(authToken, id),
          getScheduledPosts(authToken, id),
          getCreditBalances(authToken, id),
          getContacts(authToken, id),
          getOAuthStatus(authToken),
          getBusinessUsers(authToken, id),
          getBusinessDashboard(authToken, id),
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
          dashboard,
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

  const {
    business,
    connections,
    reviews,
    posts,
    balances,
    contacts,
    oauthStatus,
    attribution,
    team,
    dashboard,
  } = data;

  const aiBalance = balances.find((b) => b.credit_type === "ai")?.balance ?? "0";
  const waBalance = balances.find((b) => b.credit_type === "whatsapp")?.balance ?? "0";

  const subtitle = [business.category, business.tier, business.area]
    .filter(Boolean)
    .join(" · ");

  return (
    <AppShell
      title={business.name}
      subtitle={subtitle}
      onEditBusiness={canWrite ? () => setEditOpen(true) : undefined}
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        {business.subscription_status && (
          <div className="flex justify-end">
            <StatusBadge status={business.subscription_status} />
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard icon={Link2} label="Platform connections" value={connections.length} />
          <StatCard icon={Sparkles} label="AI credit" value={aiBalance} />
          <StatCard icon={MessagesSquare} label="WhatsApp credit" value={waBalance} />
          <StatCard icon={Star} label="Reviews synced" value={reviews.length} />
          {attribution?.signal_completeness_pct != null && (
            <StatCard
              icon={Activity}
              label="Signal completeness"
              value={`${attribution.signal_completeness_pct}%`}
            />
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
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
              dashboard.reply_rate_pct != null ? `${dashboard.reply_rate_pct.toFixed(0)}%` : "—"
            }
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <ReviewVolumeChart data={dashboard.review_volume} />
          <RatingDistributionChart data={dashboard.rating_distribution} />
        </div>

        {canWrite && (
          <BusinessEditDialog
            token={token}
            business={business}
            open={editOpen}
            onOpenChange={setEditOpen}
            onSaved={reload}
          />
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
      </div>
    </AppShell>
  );
}

function SectionCard({
  icon: Icon,
  title,
  action,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="size-4 text-muted-foreground" />
          {title}
        </CardTitle>
        {action && <CardAction>{action}</CardAction>}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">{children}</CardContent>
    </Card>
  );
}

function BusinessEditDialog({
  token,
  business,
  open,
  onOpenChange,
  onSaved,
}: {
  token: string;
  business: BusinessResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(business.name);
  const [pincode, setPincode] = useState(business.pincode ?? "");
  const [area, setArea] = useState(business.area ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await updateBusiness(token, business.id, { name, pincode, area });
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
          setName(business.name);
          setPincode(business.pincode ?? "");
          setArea(business.area ?? "");
          setError(null);
        }
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Pencil className="size-4 text-muted-foreground" />
            Edit business
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
          <Input value={area} onChange={(e) => setArea(e.target.value)} placeholder="Area" />
          <Input
            value={pincode}
            onChange={(e) => setPincode(e.target.value)}
            placeholder="Pincode"
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
    <SectionCard icon={Link2} title="Platform connections">
      {connections.length === 0 ? (
        <EmptyState label="No platform connections yet." icon={Link2} />
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

      {canWrite && (
        <div className="space-y-2 border-t pt-3">
          <div className="flex flex-wrap gap-2">
            <Select value={platform} onValueChange={(v) => setPlatform(v as typeof platform)}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="gbp">GBP</SelectItem>
                <SelectItem value="meta">Meta</SelectItem>
                <SelectItem value="whatsapp">WhatsApp</SelectItem>
              </SelectContent>
            </Select>
            <Input
              value={externalId}
              onChange={(e) => setExternalId(e.target.value)}
              placeholder="External ID (e.g. locations/123)"
            />
          </div>
          <Input
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
              variant="outline"
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
              variant="outline"
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
    </SectionCard>
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
  const [paymentId, setPaymentId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!paymentId) return;
    setSaving(true);
    setError(null);
    try {
      // The backend fetches this payment from Razorpay and credits exactly
      // what it confirms was captured -- it no longer trusts a client-typed
      // amount (see gateway/api/v1/billing.py:recharge_credit).
      await rechargeCredit(token, businessId, {
        credit_type: creditType,
        razorpay_payment_id: paymentId,
      });
      setPaymentId("");
      onChanged();
    } catch {
      setError("Could not recharge credit — check the payment ID is a captured Razorpay payment.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <SectionCard icon={Wallet} title="Credit balances">
      {balances.length === 0 ? (
        <EmptyState label="No credit activity yet." icon={Wallet} />
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

      {canWrite && (
        <div className="flex flex-wrap gap-2 border-t pt-3">
          <Select value={creditType} onValueChange={(v) => setCreditType(v as typeof creditType)}>
            <SelectTrigger className="w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ai">AI</SelectItem>
              <SelectItem value="whatsapp">WhatsApp</SelectItem>
            </SelectContent>
          </Select>
          <Input
            value={paymentId}
            onChange={(e) => setPaymentId(e.target.value)}
            placeholder="Razorpay payment ID (pay_...)"
            className="min-w-48 flex-1"
          />
          <ConfirmAction
            title="Recharge credit"
            description={`Recharge ${creditType} credit using Razorpay payment ${paymentId || "?"}?`}
            onConfirm={submit}
            disabled={saving || !paymentId}
          >
            {saving ? "Recharging..." : "Recharge"}
          </ConfirmAction>
        </div>
      )}
      {error && <ErrorState message={error} />}
    </SectionCard>
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
    <SectionCard icon={Star} title="Reviews">
      {reviews.length === 0 ? (
        <EmptyState label="No reviews synced yet." icon={Star} />
      ) : (
        <ul className="space-y-3">
          {reviews.map((r) => (
            <li key={r.id} className="border-b pb-3 text-sm last:border-0 last:pb-0">
              <div className="flex items-center justify-between">
                <span className="font-medium capitalize">
                  {r.platform} {r.rating ? `★ ${r.rating}` : ""}
                </span>
                <StatusBadge status={r.response_sent_at ? "posted" : "pending"} />
              </div>
              {r.text && <p className="mt-1 text-muted-foreground">{r.text}</p>}
              {r.ai_drafted_response && (
                <p className="mt-1 text-muted-foreground/80 italic">
                  Draft: {r.ai_drafted_response}
                </p>
              )}
              {canWrite && !r.response_sent_at && (
                <div className="mt-2 flex gap-2">
                  {!r.ai_drafted_response && (
                    <Button
                      variant="outline"
                      onClick={() => draft(r.id)}
                      disabled={busyId === r.id}
                    >
                      Draft response (1 AI credit)
                    </Button>
                  )}
                  {r.ai_drafted_response && (
                    <ConfirmAction
                      title="Send response"
                      description="Send this drafted response? This is a public-facing action."
                      onConfirm={() => send(r.id)}
                      disabled={busyId === r.id}
                    >
                      Send response
                    </ConfirmAction>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {canWrite && (
        <div className="space-y-2 border-t pt-3">
          <p className="text-xs text-muted-foreground">
            Add a test review (dev-only stand-in for a real GBP/Meta sync).
          </p>
          <div className="flex flex-wrap gap-2">
            <Select value={rating} onValueChange={setRating}>
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[5, 4, 3, 2, 1].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} star
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Review text"
            />
          </div>
          <Button onClick={addTestReview}>Add test review</Button>
        </div>
      )}
      {error && <ErrorState message={error} />}
    </SectionCard>
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
    <SectionCard icon={CalendarClock} title="Scheduled social posts">
      {posts.length === 0 ? (
        <EmptyState label="No posts scheduled." icon={CalendarClock} />
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

      {canWrite && (
        <div className="space-y-2 border-t pt-3">
          <div className="flex flex-wrap gap-2">
            <Select value={platform} onValueChange={setPlatform}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="meta">Meta</SelectItem>
                <SelectItem value="instagram">Instagram</SelectItem>
              </SelectContent>
            </Select>
            <Input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              className="w-auto"
            />
          </div>
          <Input
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
    </SectionCard>
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
    <SectionCard icon={MessagesSquare} title="WhatsApp contacts">
      {contacts.length === 0 ? (
        <EmptyState label="No contacts yet." icon={MessagesSquare} />
      ) : (
        <ul className="space-y-1">
          {contacts.map((c) => (
            <li key={c.id} className="flex items-center justify-between text-sm">
              <span className="font-mono">{c.phone_e164}</span>
              <StatusBadge status={c.opt_in ? "healthy" : "broken"} />
            </li>
          ))}
        </ul>
      )}

      {canWrite && (
        <div className="flex gap-2 border-t pt-3">
          <Input
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
    </SectionCard>
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
    <SectionCard icon={Send} title="WhatsApp campaigns">
      <p className="text-xs text-muted-foreground">
        Sends to all {optedInCount} opted-in contact(s) — real messages, real credit.
      </p>
      <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Campaign name" />
      <Input
        value={templateName}
        onChange={(e) => setTemplateName(e.target.value)}
        placeholder="Template name (must exist in Gallabox)"
      />
      <Select value={category} onValueChange={(v) => setCategory(v as typeof category)}>
        <SelectTrigger className="w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="utility">Utility</SelectItem>
          <SelectItem value="marketing">Marketing</SelectItem>
          <SelectItem value="authentication">Authentication</SelectItem>
        </SelectContent>
      </Select>
      {error && <ErrorState message={error} />}
      {result && <p className="text-sm text-muted-foreground">{result}</p>}
      <ConfirmAction
        title="Send campaign"
        description={`Send "${name || "this campaign"}" to ${optedInCount} opted-in contact(s) now?`}
        onConfirm={submit}
        disabled={sending || !name || !templateName}
      >
        {sending ? "Sending..." : "Send campaign"}
      </ConfirmAction>
    </SectionCard>
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
    <SectionCard icon={TrendingUp} title="Attribution">
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
          <li className="text-xs text-muted-foreground">
            Computed {new Date(summary.computed_at).toLocaleString()}
          </li>
        </ul>
      ) : (
        <EmptyState label="No attribution correlation computed yet." icon={TrendingUp} />
      )}
      {canWrite && (
        <div className="border-t pt-3">
          {error && <ErrorState message={error} />}
          <Button onClick={trigger} disabled={queued}>
            {queued ? "Queued — recomputing..." : "Recompute (last 7 days)"}
          </Button>
        </div>
      )}
    </SectionCard>
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
    <SectionCard icon={Users} title="Team">
      {team.length === 0 ? (
        <EmptyState label="No users on this business yet." icon={Users} />
      ) : (
        <ul className="space-y-2">
          {team.map((u) => (
            <li key={u.id} className="flex items-center justify-between text-sm">
              <span>{u.email}</span>
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
    </SectionCard>
  );
}
