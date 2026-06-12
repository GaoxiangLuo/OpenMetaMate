# Digest-pinned, aligned with the Node 22 toolchain used in CI/deploy;
# Dependabot (docker ecosystem) opens PRs to bump this
FROM node:22.22.3-alpine3.24@sha256:9385cd9f3001dfc3431e8ead12c43e9e1f87cc1b9b5c6cfd0f73865d405b27c4

WORKDIR /app

# Copy package files (.pnpmfile.cjs is required: the lockfile records its
# checksum, and frozen installs fail without it)
COPY frontend/package*.json ./
COPY frontend/pnpm-lock.yaml* ./
COPY frontend/.pnpmfile.cjs ./

# Install pnpm (pinned for reproducible builds; upgrade deliberately via PR)
# and dependencies exactly as locked
RUN npm install -g pnpm@10.34.3
RUN pnpm install --frozen-lockfile

# Copy application code
COPY frontend/ .

# Copy shared assets to where the app expects them
RUN mkdir -p ../assets/codebook
COPY assets/codebook/default.json ../assets/codebook/

# Build the application
RUN pnpm build

# Expose port
EXPOSE 3000

# Start the application
CMD ["pnpm", "start"]