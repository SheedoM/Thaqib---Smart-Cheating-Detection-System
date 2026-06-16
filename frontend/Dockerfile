FROM node:22-alpine AS build

WORKDIR /app
RUN npm install -g npm@11.6.2
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG VITE_API_URL=
ARG VITE_WS_ORIGIN=
ENV VITE_API_URL=$VITE_API_URL \
    VITE_WS_ORIGIN=$VITE_WS_ORIGIN
RUN npm run build

FROM nginx:1.29-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz >/dev/null || exit 1
