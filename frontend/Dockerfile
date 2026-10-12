# ==============================================================================
# The Lenny Growth Assistant - React Vite Frontend Multi-Stage Container
# ==============================================================================

# Stage 1: Build static assets reproducibly using Node 20
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency manifests
COPY package.json package-lock.json ./

# Deterministic dependency installation
RUN npm ci

# Accept browser-accessible API base URL at build time (defaults to http://localhost:8000)
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Copy frontend source files
COPY index.html vite.config.js ./
COPY public/ ./public/
COPY src/ ./src/

# Compile production bundle
RUN npm run build

# Stage 2: Serve static bundle with lightweight Nginx
FROM nginx:alpine-slim

# Copy custom Nginx configuration with reverse proxy and SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy production build from build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# Container health probe
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
