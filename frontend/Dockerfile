# frontend/Dockerfile
#
# Multi-stage build relying on next.config.ts's output:"standalone" --
# the final stage only copies the traced subset of node_modules Next.js
# actually needs to run `node server.js`, not the full devDependency tree.
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# No NEXT_PUBLIC_API_BASE_URL build arg: production serves the frontend
# and API on the same origin (see docker-compose.yml's Traefik path
# routing), so lib/api.ts's empty-string default (relative fetch) is
# exactly what's wanted here -- nothing to bake in at build time.
RUN npm run build

FROM node:20-slim AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
