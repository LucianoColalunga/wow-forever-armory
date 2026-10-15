FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S wfa && adduser -S wfa -G wfa
COPY --from=build --chown=wfa:wfa /app/.next/standalone ./
COPY --from=build --chown=wfa:wfa /app/.next/static ./.next/static
USER wfa
EXPOSE 3000
# API_INTERNAL_URL se lee en tiempo de ejecución (proxy /api y Server Components).
CMD ["node", "server.js"]
