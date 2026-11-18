# syntax=docker/dockerfile:1

# =============================================================================
# Stage 1: base
# =============================================================================
FROM node:22-slim AS base

WORKDIR /app

# =============================================================================
# Stage 2: builder
# =============================================================================
FROM base AS builder

COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY . .
RUN npm run build

# =============================================================================
# Stage 3: development
# =============================================================================
FROM base AS development

COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# =============================================================================
# Stage 4: production (final default stage)
# =============================================================================
FROM nginxinc/nginx-unprivileged:alpine AS production

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
