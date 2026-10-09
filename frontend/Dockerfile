# =========================================================================
# HydraControl Frontend — Production Multi-Stage Build
# Stage 1: Build static assets using Node.js
# Stage 2: Serve compiled React SPA via lightweight Nginx Alpine
# =========================================================================

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci || npm install

COPY . ./
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine

# Copy compiled SPA bundle
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy optimized production Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
