import type React from "react"

// Updated CodingSchemeItem
export interface CodingSchemeItem {
  id: string
  name: string
  dataType: "Text" | "Numeric" | "Boolean" // Simplified data types
  description: string
  includeInExtraction: boolean // New property
}

export interface Citation {
  pageNumber: number
  type: "Exact Quote" | "Inference"
  reasoning?: string | null
}

export interface ExtractionResultItem {
  value: string | number | boolean | null
  confidence?: number | null
  answerType: "Grounded" | "Inference" | "Not Found"
  citations: Citation[]
  reasoning?: string | null
  manualOverride?: boolean
}

export type ExtractionResult = Record<string, ExtractionResultItem>

export interface ChatMessage {
  id: string
  type: "user-upload" | "system" | "error" | "file-info" | "extraction-result"
  content?: string | React.ReactNode
  fileName?: string
  fileSpecificMessage?: string
  data?: ExtractionResult
  timestamp: Date
  isProcessing?: boolean
  pdfKey?: string
  codingSchemeUsed?: CodingSchemeItem[]
  historyId?: string
}

export interface ExtractionHistoryItem {
  id: string
  fileName: string
  data: ExtractionResult
  timestamp: Date
  codingSchemeUsed: CodingSchemeItem[] // Store the exact scheme used for this extraction
  pdfKey?: string
  messageId?: string
}

export interface ProcessedFileResult {
  fileName: string
  status: "success" | "error"
  data?: ExtractionResult
  errorMessage?: string
  pdfKey?: string
  messageId?: string
}
