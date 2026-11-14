FROM node:24.22.2-slim AS test
ENV TZ=UTC
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
RUN npm run typecheck
RUN npm test
