# Digest-pinned, aligned with the Node 22 toolchain used in CI/deploy;
# Dependabot (docker ecosystem) opens PRs to bump this
FROM node:26.3.0-alpine3.24@sha256:3ad34ca6292aec4a91d8ddeb9229e29d9c2f689efd0dd242860889ac71842eba

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