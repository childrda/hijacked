# Build stage: produce static assets
FROM node:20-alpine AS build
WORKDIR /app

ENV NODE_ENV=development
COPY package*.json ./
RUN npm ci --include=dev
COPY . .
RUN npm run build

# Runtime stage: nginx serves static + proxies /api to backend
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
