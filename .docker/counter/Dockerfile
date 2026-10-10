# Digest-pinned manifest list (amd64+arm64); npm ci = lockfile-exact (QEMU npm install once corrupted arm64 layers silently)
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY server.js ./

USER node

EXPOSE 3000

CMD ["npm", "start"]
