# Этап 1: сборка Vue-приложения
FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# В проде API доступен по относительному пути — nginx проксирует /api на бэкенд
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Этап 2: отдача статики через nginx
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
