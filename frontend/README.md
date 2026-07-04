# PRESENCE Admin (frontend)

Minimal read-only admin panel — built from scratch (no shared component
library reused from AgencyOS, by explicit instruction). Next.js 15 (App
Router), TypeScript, Tailwind, no other UI framework.

Talks directly to the PRESENCE gateway API (see `../gateway`); no BFF/API
routes of its own.

## Local development

```bash
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_BASE_URL
npm install
npm run dev
```

## Pages

- `/login` — email/password against `/api/v1/auth/login`
- `/` — redirects: `smb_owner` straight to their business, agency roles to
  their businesses list (`/api/v1/agencies/{agency_id}/businesses`)
- `/businesses/[id]` — profile, platform connections health, credit
  balances, reviews, scheduled social posts

Auth is a bearer JWT kept in `localStorage` (see `lib/auth-context.tsx`) —
no refresh-token rotation wired into the UI yet; re-login once the
30-minute access token expires.

## Not done yet

No production hosting/domain/Traefik route decided — dev-only for now.
No write actions (this is read-only by design for the first pass). No
agency console beyond the businesses list, no billing management UI.
