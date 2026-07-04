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

export const getConnectionsHealth = (token: string, businessId: string) =>
  request<ConnectionResponse[]>(
    `/api/v1/businesses/${businessId}/connections/health`,
    { token }
  );

export const getAgencyBusinesses = (token: string, agencyId: string) =>
  request<BusinessSummary[]>(`/api/v1/agencies/${agencyId}/businesses`, {
    token,
  });

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
