# Build stage: produce static assets
FROM node:20-alpine AS build
WORKDIR /app

# Copy dependency manifests first for layer caching
COPY package*.json ./
# Install all deps including devDependencies (tsc, vite). NODE_ENV must be
# set in same RUN so base image's production default doesn't skip dev deps.
RUN NODE_ENV=development npm ci --include=dev

# Copy source (node_modules excluded by .dockerignore)
COPY . .
# Build uses node_modules/.bin from install above
RUN npm run build
# Expose version for runtime display (survives cache; no Vite define needed)
RUN node -e "const fs=require('fs'),p=require('./package.json'); fs.writeFileSync('dist/version.json', JSON.stringify({version: p.version}))"

# Runtime stage: nginx serves static + proxies /api to backend (no Node/npm at runtime)
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN nginx -t
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
