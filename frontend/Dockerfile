# Contexte : ./frontend. L'URL de l'API est figée à la construction (vide = même origine, via le proxy).
FROM node:22.12.0-alpine3.21 AS build
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json next.config.mjs next-env.d.ts globals.d.ts ./
COPY app ./app
COPY components ./components
COPY lib ./lib
RUN npm run build

FROM node:22.12.0-alpine3.21
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY --from=build /app /app
USER node
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "-H", "0.0.0.0", "-p", "3000"]
