// lib/api.ts
//
// Thin typed fetch wrapper against the PRESENCE gateway. Deliberately no
// generated client / SDK layer for this minimal first pass -- one file,
// one function per endpoint actually used by the panel, matching the
// response_model shapes in gateway/api/v1/*.py by hand.

// Empty string = relative fetch, i.e. same origin as the page -- correct
// for production, where Traefik routes /api (and /docs, /healthz, etc.)
// on this same domain to the gateway (see docker-compose.yml's
// presence-frontend/presence-api router priority split). Only local dev,
// where the frontend runs on a different port than the API, needs this
// set explicitly (see .env.local.example).
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; token?: string | null } = {}
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.token) headers.Authorization = `Bearer ${options.token}`;

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new ApiError(res.status, detail || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// --- Auth ---

export type UserRole = "smb_owner" | "agency_admin" | "agency_viewer";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  role: UserRole;
  business_id: string | null;
  agency_id: string | null;
}

export const login = (email: string, password: string) =>
  request<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: { email, password },
  });

export const getMe = (token: string) =>
  request<UserResponse>("/api/v1/auth/me", { token });

// --- Businesses ---

export type BusinessCategory =
  | "salon_spa_gym"
  | "clinic_healthcare"
  | "fnb"
  | "retail_fashion_jewellery";
export type BusinessTier = "starter" | "growth" | "scale" | "agency";

export interface BusinessResponse {
  id: string;
  name: string;
  category: string;
  tier: string;
  agency_id: string | null;
  subscription_status: string | null;
  pincode: string | null;
  area: string | null;
}

export interface BusinessSummary {
  id: string;
  name: string;
  category: string;
  tier: string;
  subscription_status: string | null;
}

export interface ConnectionResponse {
  id: string;
  platform: "gbp" | "meta" | "whatsapp";
  provider: string | null;
  external_id: string | null;
  sync_status: "healthy" | "degraded" | "broken";
  last_synced_at: string | null;
}

export const getBusiness = (token: string, businessId: string) =>
  request<BusinessResponse>(`/api/v1/businesses/${businessId}`, { token });

export const createBusiness = (
  token: string | null,
  body: {
    name: string;
    category: BusinessCategory;
    tier: BusinessTier;
    agency_id?: string;
    pincode?: string;
    area?: string;
    invite_code?: string;
  }
) => request<BusinessResponse>("/api/v1/businesses", { method: "POST", body, token });

export const updateBusiness = (
  token: string,
  businessId: string,
  body: Partial<{
    name: string;
    category: BusinessCategory;
    tier: BusinessTier;
    pincode: string;
    area: string;
    subscription_status: string;
  }>
) =>
  request<BusinessResponse>(`/api/v1/businesses/${businessId}`, {
    method: "PATCH",
    body,
    token,
  });

export const getConnectionsHealth = (token: string, businessId: string) =>
  request<ConnectionResponse[]>(
    `/api/v1/businesses/${businessId}/connections/health`,
    { token }
  );

export const createConnection = (
  token: string,
  businessId: string,
  body: {
    platform: "gbp" | "meta" | "whatsapp";
    provider?: string;
    external_id?: string;
    access_token?: string;
  }
) =>
  request<ConnectionResponse>(`/api/v1/businesses/${businessId}/connections`, {
    method: "POST",
    body,
    token,
  });

export const getAgencyBusinesses = (token: string, agencyId: string) =>
  request<BusinessSummary[]>(`/api/v1/agencies/${agencyId}/businesses`, {
    token,
  });

// --- Agencies ---

export interface AgencyResponse {
  id: string;
  name: string;
  is_white_label: boolean;
  branding_config: Record<string, unknown> | null;
  revenue_share_pct: string | null;
  created_at: string;
}

export const createAgency = (body: {
  name: string;
  is_white_label?: boolean;
  revenue_share_pct?: string;
  invite_code?: string;
}) => request<AgencyResponse>("/api/v1/agencies", { method: "POST", body });

export const getAgency = (token: string, agencyId: string) =>
  request<AgencyResponse>(`/api/v1/agencies/${agencyId}`, { token });

export const updateAgency = (
  token: string,
  agencyId: string,
  body: Partial<{
    name: string;
    is_white_label: boolean;
    branding_config: Record<string, unknown>;
    revenue_share_pct: string;
  }>
) =>
  request<AgencyResponse>(`/api/v1/agencies/${agencyId}`, {
    method: "PATCH",
    body,
    token,
  });

// --- Users ---

export interface UserSummary {
  id: string;
  email: string;
  role: UserRole;
  business_id: string | null;
  agency_id: string | null;
  is_active: boolean;
}

export const getBusinessUsers = (token: string, businessId: string) =>
  request<UserSummary[]>(`/api/v1/businesses/${businessId}/users`, { token });

export const getAgencyUsers = (token: string, agencyId: string) =>
  request<UserSummary[]>(`/api/v1/agencies/${agencyId}/users`, { token });

export const updateUser = (
  token: string,
  userId: string,
  body: Partial<{
    role: UserRole;
    business_id: string;
    agency_id: string;
    is_active: boolean;
  }>
) => request<UserSummary>(`/api/v1/users/${userId}`, { method: "PATCH", body, token });

// --- WhatsApp ---

export interface ContactResponse {
  id: string;
  business_id: string;
  phone_e164: string;
  opt_in: boolean;
  tags: Record<string, unknown> | null;
}

export const getContacts = (token: string, businessId: string) =>
  request<ContactResponse[]>(`/api/v1/businesses/${businessId}/contacts`, {
    token,
  });

export const createContact = (
  token: string,
  body: { business_id: string; phone_e164: string; opt_in?: boolean }
) => request<ContactResponse>("/api/v1/contacts", { method: "POST", body, token });

export interface CampaignResponse {
  id: string;
  business_id: string;
  name: string;
  template_name: string;
  category: string;
  status: string;
}

export interface CampaignSendSummary {
  campaign: CampaignResponse;
  sent: number;
  failed: number;
  skipped_insufficient_credit: number;
}

export const createCampaign = (
  token: string,
  body: {
    business_id: string;
    name: string;
    template_name: string;
    category: "marketing" | "utility" | "authentication";
    contact_ids?: string[];
  }
) => request<CampaignSendSummary>("/api/v1/campaigns", { method: "POST", body, token });

// --- Reviews ---

export interface ReviewResponse {
  id: string;
  business_id: string;
  platform: "gbp" | "meta" | "whatsapp";
  rating: number | null;
  text: string | null;
  ai_drafted_response: string | null;
  response_sent_at: string | null;
}

export const getReviews = (token: string, businessId: string) =>
  request<ReviewResponse[]>(`/api/v1/businesses/${businessId}/reviews`, {
    token,
  });

export const createReview = (
  token: string,
  businessId: string,
  body: { platform: "gbp" | "meta" | "whatsapp"; rating?: number; text?: string }
) =>
  request<ReviewResponse>(`/api/v1/businesses/${businessId}/reviews`, {
    method: "POST",
    body,
    token,
  });

export const draftReviewResponse = (token: string, reviewId: string) =>
  request<{ review: ReviewResponse; cache_hit: boolean }>(
    `/api/v1/reviews/${reviewId}/draft-response`,
    { method: "POST", token }
  );

export const sendReviewResponse = (token: string, reviewId: string) =>
  request<ReviewResponse>(`/api/v1/reviews/${reviewId}/send-response`, {
    method: "POST",
    token,
  });

// --- Social ---

export interface ScheduledPostResponse {
  id: string;
  business_id: string;
  platform: string;
  content: string;
  media_url: string | null;
  scheduled_at: string;
  status: string;
  posted_at: string | null;
}

export const getScheduledPosts = (token: string, businessId: string) =>
  request<ScheduledPostResponse[]>(
    `/api/v1/businesses/${businessId}/social/posts`,
    { token }
  );

export const createScheduledPost = (
  token: string,
  businessId: string,
  body: { platform: string; content: string; media_url?: string; scheduled_at: string }
) =>
  request<ScheduledPostResponse>(`/api/v1/businesses/${businessId}/social/posts`, {
    method: "POST",
    body,
    token,
  });

// --- Billing ---

export interface BalanceResponse {
  business_id: string;
  credit_type: "ai" | "whatsapp";
  balance: string;
}

export const getCreditBalances = (token: string, businessId: string) =>
  request<BalanceResponse[]>(`/api/v1/credit-ledger/${businessId}/balance`, {
    token,
  });

export const rechargeCredit = (
  token: string,
  businessId: string,
  body: { credit_type: "ai" | "whatsapp"; razorpay_payment_id: string }
) =>
  request<BalanceResponse>(`/api/v1/credit-ledger/${businessId}/recharge`, {
    method: "POST",
    body,
    token,
  });

export interface SubscriptionResponse {
  id: string;
  business_id: string;
  razorpay_subscription_id: string | null;
  status: string;
}

export const createSubscription = (
  token: string,
  body: { business_id: string; plan_id: string; total_count?: number }
) =>
  request<SubscriptionResponse>("/api/v1/billing/subscriptions", {
    method: "POST",
    body,
    token,
  });

// --- Attribution ---

export interface AttributionSummary {
  business_id: string;
  period_start: string;
  period_end: string;
  correlation_score: number | null;
  signal_completeness_pct: number | null;
  computed_at: string;
}

export const getAttributionSummary = (token: string, businessId: string) =>
  request<AttributionSummary>(`/api/v1/businesses/${businessId}/attribution/summary`, {
    token,
  });

export const triggerComputeCorrelation = (
  token: string,
  body: { business_id: string; period_start: string; period_end: string }
) =>
  request<{ status: string }>("/api/v1/attribution/compute-correlation", {
    method: "POST",
    body,
    token,
  });

// --- OAuth ---

export interface OAuthStatusResponse {
  gbp_configured: boolean;
  meta_configured: boolean;
}

export const getOAuthStatus = (token: string) =>
  request<OAuthStatusResponse>("/api/v1/oauth/status", { token });

// --- Dashboard ---

export interface ReviewVolumePoint {
  date: string;
  count: number;
}

export interface RatingBucket {
  rating: number;
  count: number;
}

export interface DashboardStats {
  avg_rating: number | null;
  reviews_this_month: number;
  pending_replies: number;
  reply_rate_pct: number | null;
  review_volume: ReviewVolumePoint[];
  rating_distribution: RatingBucket[];
}

export interface BusinessDashboard extends DashboardStats {
  business_id: string;
}

export interface AgencyDashboard extends DashboardStats {
  agency_id: string;
  active_businesses: number;
  total_businesses: number;
}

export const getBusinessDashboard = (token: string, businessId: string) =>
  request<BusinessDashboard>(`/api/v1/businesses/${businessId}/dashboard`, {
    token,
  });

export const getAgencyDashboard = (token: string, agencyId: string) =>
  request<AgencyDashboard>(`/api/v1/agencies/${agencyId}/dashboard`, {
    token,
  });
