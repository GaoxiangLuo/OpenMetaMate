FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./
COPY frontend/pnpm-lock.yaml* ./

# Install pnpm (pinned to the 10.x line matching pnpm-lock.yaml; unpinned this
# installs pnpm 11, which does not match the v9 lockfile) and dependencies
RUN npm install -g pnpm@10.34.3
RUN pnpm install

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