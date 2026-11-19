// API Configuration
const isDevelopment = process.env.NODE_ENV === "development"

export const config = {
  // API endpoint from environment or local development fallback
  apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",

  // File upload limits (must match backend/app/core/config.py)
  MAX_FILE_SIZE_MB: 10,
  MAX_FILES_PER_BATCH: 100,
  ALLOWED_FILE_TYPES: ["application/pdf"],

  // Rate limiting (must match backend EXTRACTION_RATE_LIMIT_PER_MINUTE)
  EXTRACTION_RATE_LIMIT_PER_MINUTE: 20,

  // UI Configuration
  // Colour bands for the confidence indicator. The score is a verification probability
  // from a decision model and clusters near 1, so the green band starts high: in offline
  // validation against human-coded papers, values at or above 0.99 were right about 90% of
  // the time, 0.85-0.99 about 70%, and below 0.85 about half.
  CONFIDENCE_THRESHOLDS: {
    HIGH: 0.99,
    MEDIUM: 0.85,
  },

  // Development flags
  isDevelopment,
  isProduction: process.env.NODE_ENV === "production",
}

export default config
