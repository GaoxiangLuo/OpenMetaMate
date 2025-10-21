"use client"

import type React from "react"
import dynamic from "next/dynamic"
import { useState, useRef, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import {
  FileText,
  Settings2,
  BotMessageSquare,
  BarChart3,
  Download,
  Paperclip,
  Send,
  Trash2,
  Eye,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  MessageSquareText,
  InfoIcon,
  Activity,
} from "lucide-react"
import CodingSchemeEditor from "@/components/coding-scheme-editor"
import ExtractionItemDisplay from "@/components/extraction-item-display"
import AuthorInfoModal from "@/components/author-info-modal"
const PdfViewerPanel = dynamic(() => import("@/components/pdf-viewer-panel"), {
  ssr: false,
})
import ResizablePanelContainer from "@/components/resizable-panel-container"
import type {
  CodingSchemeItem,
  ChatMessage,
  ExtractionHistoryItem,
  ProcessedFileResult,
  ExtractionResult,
  ExtractionResultItem,
  Citation,
} from "@/lib/types"
import config from "@/lib/config"

// Import the comprehensive default coding scheme
import defaultCodingSchemeData from "@assets/codebook/default.json"

const defaultCodingScheme: CodingSchemeItem[] = defaultCodingSchemeData as CodingSchemeItem[]

const PDF_SOURCE_LIMIT = 50

// Initialize without timestamp to avoid hydration issues
const getInitialMessages = (): ChatMessage[] => [
  {
    id: "welcome",
    type: "system",
    content:
      "Welcome to MetaMate! I'm your AI assistant for automated data extraction from systematic reviews and meta-analyses. To get started, simply upload one or more PDF files (conference papers, journals, theses, reports, etc.) and MetaMate will extract structured data based on your coding scheme. For more details about accuracy, please refer to our research paper.",
    timestamp: new Date(),
  },
]

// Helper to convert all extractions to a single CSV string
const convertAllExtractionsToCSV = (history: ExtractionHistoryItem[]): string => {
  if (history.length === 0) return ""

  const allRows: Record<string, string | number | boolean>[] = []
  // Dynamically build headers based on what was actually extracted and included in the scheme for each entry
  const allPossibleHeaders = new Set<string>(["FileName"])
  history.forEach((entry) => {
    entry.codingSchemeUsed.forEach((schemeItem: CodingSchemeItem) => {
      if (schemeItem.includeInExtraction) {
        // Only consider items that were marked for inclusion
        allPossibleHeaders.add(schemeItem.name)
      }
    })
  })

  const sortedHeaders = Array.from(allPossibleHeaders).sort((a, b) => {
    if (a === "FileName") return -1 // FileName always first
    if (b === "FileName") return 1
    if (a < b) return -1
    if (a > b) return 1
    return 0
  })

  history.forEach((entry) => {
    const row: Record<string, string | number | boolean> = { FileName: entry.fileName }
    // Iterate over the scheme used for *this specific entry*
    entry.codingSchemeUsed.forEach((schemeItem) => {
      if (!schemeItem.includeInExtraction) {
        return
      }

      const resultItem = entry.data[schemeItem.name]
      if (!resultItem) {
        return
      }

      const rawValue = resultItem.value as unknown

      if (Array.isArray(rawValue)) {
        const displayValue = rawValue
          .filter((item): item is string | number | boolean => item !== null && item !== undefined)
          .join("; ")
        row[schemeItem.name] = displayValue
        return
      }

      const normalizedValue = (resultItem.value ?? "") as string | number | boolean
      row[schemeItem.name] = normalizedValue
    })
    allRows.push(row)
  })

  const headerRow = sortedHeaders.join(",")
  const dataRows = allRows.map((row) => {
    return sortedHeaders
      .map((header) => {
        const value = row[header] ?? "" // Use empty string for missing values (e.g. if scheme changed)
        const escapedValue = String(value).replace(/"/g, '""')
        return `"${escapedValue}"`
      })
      .join(",")
  })

  return [headerRow, ...dataRows].join("\n")
}

// Call the FastAPI backend for real extraction
const callExtractionAPI = async (file: File, scheme: CodingSchemeItem[]): Promise<ExtractionResult> => {
  const formData = new FormData()
  formData.append("pdf_file", file)
  formData.append("coding_scheme", JSON.stringify(scheme))

  console.log(`Calling extraction API: ${config.apiUrl}/api/v1/extract`)
  const response = await fetch(`${config.apiUrl}/api/v1/extract`, {
    method: "POST",
    body: formData,
  })

  if (!response.ok) {
    console.error(`API call failed with status: ${response.status}`)
    const errorData = await response.json().catch(() => ({ detail: "Unknown error" }))
    console.error("Error details:", errorData)

    // Provide more specific error messages based on status code
    if (response.status === 429) {
      throw new Error("Rate limit exceeded. Maximum 10 files per minute. Please wait before trying again.")
    } else if (response.status === 413) {
      throw new Error("File too large. Maximum file size is 10MB.")
    } else if (response.status === 401) {
      throw new Error("API authentication failed. Please check the API key configuration.")
    } else if (response.status === 422) {
      throw new Error(
        errorData.detail || "Failed to process the PDF. The file might be corrupted or contain no extractable text.",
      )
    } else if (response.status === 504) {
      throw new Error("Request timed out. The PDF might be too large or complex.")
    } else {
      throw new Error(errorData.detail || `Server error (${response.status}). Please try again.`)
    }
  }

  const result = await response.json()

  // Check if the response has valid data
  if (!result || !result.extractedData) {
    throw new Error("Invalid response from server: No extraction data received")
  }

  // Convert the API response format to match the UI expected format
  const extractedData: ExtractionResult = {}
  let allNotFound = true
  let hasData = false

  for (const [key, item] of Object.entries(result.extractedData)) {
    const resultItem = item as ExtractionResultItem
    extractedData[key] = {
      value: resultItem.value,
      confidence: resultItem.confidence ?? null,
      answerType: resultItem.answerType,
      citations: (resultItem.citations ?? []).map((citation) => ({
        pageNumber: citation.pageNumber,
        type: citation.type,
        reasoning: citation.reasoning ?? null,
      })),
      reasoning: resultItem.reasoning ?? null,
    }

    // Check if any value is not "Not Found"
    if (resultItem.answerType !== "Not Found") {
      allNotFound = false
    }
    hasData = true
  }

  // If all fields are "Not Found", treat it as an error
  if (hasData && allNotFound) {
    throw new Error("Extraction failed: No data could be extracted from the document. This may be due to an API error.")
  }

  return extractedData
}

export default function MetaMateChatPage() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isSchemeEditorOpen, setIsSchemeEditorOpen] = useState(false)
  const [codingScheme, setCodingScheme] = useState<CodingSchemeItem[]>(defaultCodingScheme)
  const [isExtracting, setIsExtracting] = useState(false)
  const [extractingFileCount, setExtractingFileCount] = useState(0)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [extractionHistory, setExtractionHistory] = useState<ExtractionHistoryItem[]>([])
  const [isAuthorInfoModalOpen, setIsAuthorInfoModalOpen] = useState(false)
  const [isClient, setIsClient] = useState(false)
  const [pdfSources, setPdfSources] = useState<Record<string, string>>({})
  const pdfSourcesRef = useRef<Record<string, string>>({})
  const pdfSourceOrderRef = useRef<string[]>([])
  const [viewerSelection, setViewerSelection] = useState<{
    pdfKey?: string
    fileName?: string
    citations: Citation[]
    activeIndex: number
  } | null>(null)
  const chatAreaRef = useRef<HTMLDivElement>(null)

  // Initialize messages on client side only to avoid hydration issues
  useEffect(() => {
    setIsClient(true)
    if (messages.length === 0) {
      setMessages(getInitialMessages())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    pdfSourcesRef.current = pdfSources
    setViewerSelection((prev) => {
      if (!prev) return prev
      if (!prev.pdfKey || !pdfSources[prev.pdfKey]) {
        return null
      }
      return prev
    })
  }, [pdfSources])

  useEffect(
    () => () => {
      Object.values(pdfSourcesRef.current).forEach((url) => URL.revokeObjectURL(url))
    },
    [],
  )

  // Scrolling function for manual triggers
  const scrollToBottom = useCallback(() => {
    if (chatAreaRef.current) {
      chatAreaRef.current.scrollTo({
        top: chatAreaRef.current.scrollHeight,
        behavior: "smooth",
      })
    }
  }, [])

  const registerPdfSource = useCallback((key: string, file: File) => {
    const nextUrl = URL.createObjectURL(file)
    setPdfSources((prev) => {
      const previousUrl = prev[key]
      if (previousUrl) {
        URL.revokeObjectURL(previousUrl)
      }

      const updated = { ...prev, [key]: nextUrl }
      const order = pdfSourceOrderRef.current
      const existingIndex = order.indexOf(key)
      if (existingIndex !== -1) {
        order.splice(existingIndex, 1)
      }
      order.push(key)

      while (order.length > PDF_SOURCE_LIMIT) {
        const oldestKey = order.shift()
        if (!oldestKey) {
          break
        }
        const urlToRemove = updated[oldestKey]
        if (urlToRemove) {
          URL.revokeObjectURL(urlToRemove)
          delete updated[oldestKey]
        }
      }

      pdfSourcesRef.current = updated
      return updated
    })
    return nextUrl
  }, [])

  const addMessage = useCallback((message: Omit<ChatMessage, "id" | "timestamp"> & { id?: string }) => {
    setMessages((prevMessages) => [
      ...prevMessages,
      {
        ...(message as Omit<ChatMessage, "id" | "timestamp">),
        id: message.id || Date.now().toString() + Math.random().toString(36).substring(2, 7),
        timestamp: new Date(),
      } as ChatMessage,
    ])
  }, [])

  const updateMessage = useCallback((id: string, updates: Partial<ChatMessage>) => {
    setMessages((prev) => prev.map((msg) => (msg.id === id ? { ...msg, ...updates } : msg)))
  }, [])

  const selectPdfForViewer = useCallback(
    (fileKey: string | undefined, fileName: string | undefined, citations: Citation[], index: number) => {
      if (!fileKey) {
        addMessage({ type: "error", content: "PDF source unavailable for this extraction." })
        return
      }

      const pdfUrl = pdfSourcesRef.current[fileKey]
      if (!pdfUrl) {
        addMessage({ type: "error", content: "PDF preview is not available. Please re-upload the document." })
        return
      }

      const safeIndex = citations.length > 0 ? Math.min(Math.max(index, 0), citations.length - 1) : 0
      setViewerSelection({
        pdfKey: fileKey,
        fileName: fileName ?? "PDF Document",
        citations,
        activeIndex: safeIndex,
      })
    },
    [addMessage],
  )

  const applyExtractionEdit = useCallback(
    (messageId: string, historyId: string | undefined, field: string, updatedItem: ExtractionResultItem) => {
      setMessages((prevMessages) =>
        prevMessages.map((msg) => {
          if (msg.type !== "extraction-result" || !msg.data) {
            return msg
          }
          const matchesHistory = historyId ? msg.historyId === historyId : false
          const matchesMessage = msg.id === messageId
          if (!matchesHistory && !matchesMessage) {
            return msg
          }
          return {
            ...msg,
            data: {
              ...msg.data,
              [field]: { ...updatedItem },
            },
          }
        }),
      )

      setExtractionHistory((prevHistory) =>
        prevHistory.map((entry) => {
          const matchesHistory = historyId ? entry.id === historyId : false
          const matchesMessage = entry.messageId ? entry.messageId === messageId : false
          if (!matchesHistory && !matchesMessage) {
            return entry
          }
          return {
            ...entry,
            data: {
              ...entry.data,
              [field]: { ...updatedItem },
            },
          }
        }),
      )
    },
    [setMessages, setExtractionHistory],
  )

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      const newFiles = Array.from(event.target.files).filter((file) => file.type === "application/pdf")
      const invalidFiles = Array.from(event.target.files).filter((file) => file.type !== "application/pdf")

      if (invalidFiles.length > 0) {
        addMessage({
          type: "error",
          content: `Invalid file type(s): ${invalidFiles.map((f) => f.name).join(", ")}. Only PDFs are accepted.`,
        })
      }

      if (newFiles.length > 0) {
        setSelectedFiles((prev) => [...prev, ...newFiles])
        addMessage({
          type: "user-upload",
          content: `Selected ${newFiles.length} PDF(s) for extraction.`,
        })

        // Immediate scroll to bottom when files are selected
        setTimeout(scrollToBottom, 200)
      }
      event.target.value = ""
    }
  }

  const triggerFileInput = () => {
    fileInputRef.current?.click()
  }

  const handleSaveSchemeInApp = (updatedScheme: CodingSchemeItem[]) => {
    setCodingScheme(updatedScheme) // This updates the scheme for new extractions
    // No system message here, toast in editor is enough
  }

  const processSingleFile = async (file: File, currentScheme: CodingSchemeItem[]): Promise<ProcessedFileResult> => {
    const uniqueSuffix = `${Date.now().toString()}_${Math.random().toString(36).substring(2, 9)}`
    const fileMessageId = `file_msg_${uniqueSuffix}_${file.name.replace(/[^a-zA-Z0-9_.-]/g, "")}`
    const fileKey = `pdf_${uniqueSuffix}`

    registerPdfSource(fileKey, file)

    setViewerSelection({
      pdfKey: fileKey,
      fileName: file.name,
      citations: [],
      activeIndex: 0,
    })

    addMessage({
      id: fileMessageId,
      type: "file-info",
      fileName: file.name,
      fileSpecificMessage: `Starting extraction...`,
      isProcessing: true,
    })

    try {
      // Call the real API with the file and full scheme (API will filter includeInExtraction)
      const extractedData = await callExtractionAPI(file, currentScheme)
      const schemeSnapshot = currentScheme.map((item) => ({ ...item }))

      updateMessage(fileMessageId, {
        isProcessing: false,
        fileSpecificMessage: `Extraction successful.`,
        data: extractedData,
        type: "extraction-result",
        pdfKey: fileKey,
        codingSchemeUsed: schemeSnapshot,
      })

      const firstGroundedCitations =
        Object.values(extractedData).find((item) => item.citations && item.citations.length > 0)?.citations ?? []

      if (firstGroundedCitations.length > 0) {
        selectPdfForViewer(fileKey, file.name, firstGroundedCitations, 0)
      }
      return { fileName: file.name, status: "success", data: extractedData, pdfKey: fileKey, messageId: fileMessageId }
    } catch (error) {
      const errorMessage = (error as Error).message
      updateMessage(fileMessageId, {
        isProcessing: false,
        fileSpecificMessage: `❌ ${errorMessage}`,
        type: "error",
        data: undefined,
      })
      return { fileName: file.name, status: "error", errorMessage: errorMessage, messageId: fileMessageId }
    }
  }

  const handleExtractData = async () => {
    if (selectedFiles.length === 0) {
      addMessage({ type: "error", content: "Please select one or more PDF files first." })
      return
    }
    setIsExtracting(true)
    const filesToProcess = [...selectedFiles]
    setExtractingFileCount(selectedFiles.length)
    setSelectedFiles([])

    addMessage({ type: "system", content: `Starting batch extraction for ${filesToProcess.length} file(s)...` })

    // Important: Use a deep copy of the codingScheme as it is AT THIS MOMENT for the entire batch
    const schemeForThisBatch = JSON.parse(JSON.stringify(codingScheme)) as CodingSchemeItem[]

    // Process all files concurrently
    const results = await Promise.all(filesToProcess.map((file) => processSingleFile(file, schemeForThisBatch)))

    // Add successful extractions to history
    results.forEach((result, index) => {
      if (result.status === "success" && result.data) {
        const newHistoryEntry: ExtractionHistoryItem = {
          id: Date.now().toString() + index + result.fileName,
          fileName: result.fileName,
          data: result.data,
          timestamp: new Date(),
          codingSchemeUsed: schemeForThisBatch, // Store the scheme used for this specific extraction
          pdfKey: result.pdfKey,
          messageId: result.messageId,
        }
        setExtractionHistory((prev) => [newHistoryEntry, ...prev.slice(0, 19)])
        if (result.messageId) {
          updateMessage(result.messageId, { historyId: newHistoryEntry.id })
        }
      }
    })

    const successCount = results.filter((r) => r.status === "success").length
    const failedCount = results.filter((r) => r.status === "error").length
    const failedFiles = results.filter((r) => r.status === "error")

    let completionMessage = `Batch extraction complete. ${successCount} succeeded, ${failedCount} failed.`

    // Add details about failures if any
    if (failedCount > 0 && failedFiles.length > 0) {
      const errorTypes = new Map<string, number>()

      failedFiles.forEach((f) => {
        if (f.errorMessage?.includes("Rate limit")) {
          errorTypes.set("rate_limit", (errorTypes.get("rate_limit") || 0) + 1)
        } else if (f.errorMessage?.includes("temperature")) {
          errorTypes.set("temperature", (errorTypes.get("temperature") || 0) + 1)
        } else if (f.errorMessage?.includes("400") || f.errorMessage?.includes("Bad Request")) {
          errorTypes.set("bad_request", (errorTypes.get("bad_request") || 0) + 1)
        } else if (f.errorMessage?.includes("authentication") || f.errorMessage?.includes("401")) {
          errorTypes.set("auth", (errorTypes.get("auth") || 0) + 1)
        } else if (f.errorMessage?.includes("timeout") || f.errorMessage?.includes("504")) {
          errorTypes.set("timeout", (errorTypes.get("timeout") || 0) + 1)
        } else if (f.errorMessage?.includes("File too large") || f.errorMessage?.includes("413")) {
          errorTypes.set("file_size", (errorTypes.get("file_size") || 0) + 1)
        } else {
          errorTypes.set("other", (errorTypes.get("other") || 0) + 1)
        }
      })

      const errorDetails: string[] = []
      if (errorTypes.get("rate_limit")) errorDetails.push(`${errorTypes.get("rate_limit")} hit rate limit`)
      if (errorTypes.get("temperature")) errorDetails.push(`${errorTypes.get("temperature")} temperature config error`)
      if (errorTypes.get("bad_request")) errorDetails.push(`${errorTypes.get("bad_request")} bad request`)
      if (errorTypes.get("auth")) errorDetails.push(`${errorTypes.get("auth")} authentication failed`)
      if (errorTypes.get("timeout")) errorDetails.push(`${errorTypes.get("timeout")} timed out`)
      if (errorTypes.get("file_size")) errorDetails.push(`${errorTypes.get("file_size")} file too large`)
      if (errorTypes.get("other")) errorDetails.push(`${errorTypes.get("other")} other errors`)

      if (errorDetails.length > 0) {
        completionMessage += ` (${errorDetails.join(", ")})`
      }
    }

    addMessage({
      type: "system",
      content: completionMessage,
    })
    setIsExtracting(false)
    setExtractingFileCount(0)
  }

  const downloadAllHistoryCSV = () => {
    if (extractionHistory.length === 0) {
      addMessage({ type: "error", content: "No extraction history to download." })
      return
    }
    const csvData = convertAllExtractionsToCSV(extractionHistory)
    const blob = new Blob([csvData], { type: "text/csv;charset=utf-8;" })
    const link = document.createElement("a")
    link.href = URL.createObjectURL(blob)
    link.download = `MetaMate_All_Extractions_${new Date().toISOString().split("T")[0]}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(link.href)
    addMessage({ type: "system", content: "Downloaded all extraction history as CSV." })
  }

  const viewHistoryItem = (item: ExtractionHistoryItem) => {
    addMessage({
      type: "user-upload",
      content: (
        <div className="flex items-center gap-2">
          <MessageSquareText className="h-4 w-4 text-white/80" />
          <span>Show extraction for: {item.fileName}</span>
        </div>
      ),
    })
    addMessage({
      type: "extraction-result",
      fileName: item.fileName,
      fileSpecificMessage: "", // Removed verbose message to keep UI clean
      data: item.data,
      pdfKey: item.pdfKey,
      codingSchemeUsed: item.codingSchemeUsed,
      historyId: item.id,
    })

    const firstGroundedCitations =
      Object.values(item.data).find((resultItem) => resultItem.citations && resultItem.citations.length > 0)
        ?.citations ?? []

    if (item.pdfKey && firstGroundedCitations.length > 0) {
      selectPdfForViewer(item.pdfKey, item.fileName, firstGroundedCitations, 0)
    }

    // Immediate scroll to bottom when viewing extraction
    setTimeout(scrollToBottom, 300) // Slightly longer delay since we're adding two messages
  }

  const removeSelectedFile = (fileNameToRemove: string) => {
    setSelectedFiles((prev) => prev.filter((f) => f.name !== fileNameToRemove))
  }

  const activePdfUrl = viewerSelection?.pdfKey ? pdfSources[viewerSelection.pdfKey] : undefined
  const activePdfName = viewerSelection?.fileName
  const activeCitations = viewerSelection?.citations ?? []
  const activeCitationIndex = viewerSelection?.activeIndex ?? 0

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-200 font-sans">
      <div className="flex flex-1 overflow-hidden">
        <ResizablePanelContainer
          initialLeftRatio={0.5}
          minLeftWidth={360}
          minRightWidth={360}
          left={
            <div className="flex flex-col h-full min-w-0">
              {/* Header */}
              <header className="p-3.5 border-b border-slate-200 dark:border-slate-700/60 bg-white dark:bg-primary-jhuBlue flex justify-between items-center shadow-subtle">
                <div className="flex items-center gap-2.5">
                  <BotMessageSquare className="h-7 w-7 text-primary-jhuBlue dark:text-primary-jhuLightBlue" />
                  <h1 className="text-xl font-semibold text-primary-jhuBlue dark:text-white tracking-tight">
                    MetaMate
                  </h1>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsAuthorInfoModalOpen(true)}
                    className="text-xs py-1 px-2 text-primary-jhuBlue dark:text-primary-jhuLightBlue hover:bg-primary-jhuLightBlue/10 dark:hover:bg-primary-jhuBlue/80"
                  >
                    <InfoIcon className="mr-1 h-3.5 w-3.5" /> About & Cite
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => window.open("https://metamate.statuspage.io/", "_blank")}
                    className="text-xs py-1 px-2 text-primary-jhuBlue dark:text-primary-jhuLightBlue hover:bg-primary-jhuLightBlue/10 dark:hover:bg-primary-jhuBlue/80"
                  >
                    <Activity className="mr-1 h-3.5 w-3.5" /> Status
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setIsSchemeEditorOpen(true)}
                    className="text-sm py-1.5 px-3 text-primary-jhuBlue dark:text-primary-jhuLightBlue border-primary-jhuBlue/70 dark:border-primary-jhuLightBlue/70 hover:bg-primary-jhuLightBlue/10 dark:hover:bg-primary-jhuBlue/80"
                  >
                    <Settings2 className="mr-1.5 h-4 w-4" />
                    Coding Scheme
                  </Button>
                </div>
              </header>

              {/* Messages Area */}
              <div className="flex-1 overflow-hidden bg-slate-100 dark:bg-slate-800/30">
                <div ref={chatAreaRef} className="h-full overflow-y-auto p-4 space-y-4">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.type === "user-upload" ? "justify-end" : "justify-start"} mb-3.5`}
                    >
                      <div
                        className={`max-w-2xl ${msg.type === "error" && msg.fileName ? "p-2" : "p-3"} rounded-lg shadow-medium text-sm leading-relaxed ${
                          msg.type === "user-upload"
                            ? "bg-primary-jhuLightBlue text-white"
                            : msg.type === "system"
                              ? "bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-100"
                              : msg.type === "error"
                                ? "bg-red-100 dark:bg-red-900/50 border border-red-300 dark:border-red-700 text-red-700 dark:text-red-200"
                                : "bg-white dark:bg-slate-700/80 border border-slate-200 dark:border-slate-600/70"
                        }`}
                      >
                        {msg.type === "error" && !msg.fileName && (
                          <AlertTriangle className="h-5 w-5 text-red-500 dark:text-red-400 shrink-0" />
                        )}

                        {(msg.type === "file-info" ||
                          msg.type === "extraction-result" ||
                          (msg.type === "error" && msg.fileName)) &&
                          msg.fileName && (
                            <div
                              className={`font-semibold text-primary-jhuBlue dark:text-primary-jhuLightBlue ${msg.type === "error" ? "mb-0.5" : "mb-1"}`}
                            >
                              <FileText className="inline h-4 w-4 mr-1" />
                              {msg.fileName}
                            </div>
                          )}

                        {msg.fileSpecificMessage && (
                          <div
                            className={`text-xs ${msg.type === "error" ? "text-red-600 dark:text-red-300" : "text-slate-600 dark:text-slate-400 italic"} ${msg.type === "error" ? "" : "mb-1"}`}
                          >
                            {msg.type === "error" && <AlertTriangle className="inline h-3 w-3 mr-1" />}
                            {msg.fileSpecificMessage}
                          </div>
                        )}

                        {typeof msg.content === "string" && !msg.fileSpecificMessage ? (
                          <p>{msg.content}</p>
                        ) : (
                          msg.content
                        )}

                        {msg.isProcessing && (
                          <div className="flex items-center text-xs text-slate-500 dark:text-slate-400">
                            <Loader2 className="animate-spin mr-1.5 h-3.5 w-3.5" />
                            Processing...
                          </div>
                        )}

                        {msg.data && msg.type === "extraction-result" && (
                          <div className="mt-1.5 pt-1.5 border-t border-slate-300/70 dark:border-slate-600/70">
                            <h4 className="font-medium text-xs mb-2 text-slate-600 dark:text-slate-300">
                              <CheckCircle2 className="inline h-4 w-4 mr-1 text-jhu-accent-4" /> Extracted Data:
                            </h4>
                            <div className="space-y-2 text-xs">
                              {Object.entries(msg.data).map(([key, resultItem]) => {
                                const schemeMatch = msg.codingSchemeUsed?.find((schemeItem) => schemeItem.name === key)
                                return (
                                  <ExtractionItemDisplay
                                    key={key}
                                    label={key}
                                    item={resultItem}
                                    dataType={schemeMatch?.dataType}
                                    editable={msg.type === "extraction-result" && Boolean(msg.historyId)}
                                    onSave={(updated) => applyExtractionEdit(msg.id, msg.historyId, key, updated)}
                                    onCitationSelect={(_, index, citations) =>
                                      selectPdfForViewer(msg.pdfKey, msg.fileName, citations, index)
                                    }
                                  />
                                )
                              })}
                            </div>
                          </div>
                        )}
                        {isClient && (
                          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1.5 text-right">
                            {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Input Area */}
              <div className="p-3.5 border-t border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/60 shadow-upward">
                {selectedFiles.length > 0 && (
                  <div className="mb-2 space-y-1.5 max-h-28 overflow-y-auto pr-1">
                    {selectedFiles.map((file) => (
                      <div
                        key={file.name}
                        className="p-1.5 border border-jhu-light-blue/50 dark:border-jhu-blue/50 bg-jhu-light-blue/10 dark:bg-jhu-blue/20 rounded-md flex justify-between items-center text-xs"
                      >
                        <div className="flex items-center gap-1.5 truncate">
                          <FileText className="h-4 w-4 text-primary-jhuBlue dark:text-primary-jhuLightBlue shrink-0" />
                          <span
                            className="font-medium text-primary-jhuBlue dark:text-slate-100 truncate"
                            title={file.name}
                          >
                            {file.name}
                          </span>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeSelectedFile(file.name)}
                          className="text-red-500/80 hover:bg-red-500/10 h-6 w-6 shrink-0"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-2.5">
                  <Button
                    variant="outline"
                    onClick={triggerFileInput}
                    className="p-2.5 border-primary-jhuBlue/70 text-primary-jhuBlue hover:bg-primary-jhuLightBlue/10 dark:text-primary-jhuLightBlue dark:border-primary-jhuLightBlue/70 dark:hover:bg-primary-jhuBlue/30"
                    title="Attach PDF files"
                  >
                    <Paperclip className="h-5 w-5" />
                    <span className="sr-only">Attach PDF</span>
                  </Button>
                  <Input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    multiple
                    onChange={handleFileChange}
                    className="hidden"
                    id="pdf-upload-chat"
                  />
                  <Button
                    onClick={handleExtractData}
                    disabled={selectedFiles.length === 0 || isExtracting}
                    className="flex-1 py-2.5 bg-primary-jhuBlue hover:bg-primary-jhuBlue/90 text-white dark:bg-primary-jhuLightBlue dark:text-primary-jhuBlue dark:hover:bg-primary-jhuLightBlue/90 text-sm font-medium"
                  >
                    {isExtracting ? (
                      <Loader2 className="animate-spin mr-2 h-4 w-4" />
                    ) : (
                      <Send className="mr-2 h-4 w-4" />
                    )}
                    {isExtracting
                      ? `Extracting ${extractingFileCount} file(s)...`
                      : `Extract Data from ${selectedFiles.length > 0 ? selectedFiles.length + " file(s)" : "PDF(s)"}`}
                  </Button>
                </div>
              </div>
            </div>
          }
          right={
            <PdfViewerPanel
              fileUrl={activePdfUrl}
              fileName={activePdfName}
              citations={activeCitations}
              activeIndex={activeCitationIndex}
            />
          }
        />
        {/* Right Sidebar: Extraction History */}
        <aside className="w-80 border-l border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/40 flex flex-col shadow-lg">
          <CardHeader className="p-3.5 border-b border-slate-200 dark:border-slate-700/60">
            <CardTitle className="text-base font-semibold flex items-center gap-2 text-primary-jhuBlue dark:text-primary-jhuLightBlue">
              <BarChart3 className="h-5 w-5" />
              Extraction History
            </CardTitle>
            <CardDescription className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Recent extractions this session.
            </CardDescription>
          </CardHeader>
          <ScrollArea className="flex-1">
            <CardContent className="p-2.5">
              {extractionHistory.length === 0 ? (
                <p className="text-xs text-slate-500 dark:text-slate-400 text-center py-3">No extractions yet.</p>
              ) : (
                <ul className="space-y-1.5">
                  {extractionHistory.map((entry) => (
                    <li
                      key={entry.id}
                      className="p-2 rounded-md border border-slate-200 dark:border-slate-700/70 bg-slate-50 dark:bg-slate-700/40 hover:bg-slate-100 dark:hover:bg-slate-700/70 transition-colors group"
                    >
                      <div className="flex justify-between items-center">
                        <div className="truncate">
                          <p
                            className="font-medium text-xs text-primary-jhuBlue dark:text-slate-100 truncate"
                            title={entry.fileName}
                          >
                            {entry.fileName}
                          </p>
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            {entry.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-primary-jhuBlue/70 dark:text-primary-jhuLightBlue/70 group-hover:text-primary-jhuBlue dark:group-hover:text-primary-jhuLightBlue hover:bg-primary-jhuLightBlue/10 dark:hover:bg-primary-jhuBlue/30 shrink-0"
                          onClick={() => viewHistoryItem(entry)}
                          title="View this extraction in chat"
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </ScrollArea>
          {extractionHistory.length > 0 && (
            <div className="p-2.5 border-t border-slate-200 dark:border-slate-700/60">
              <Button
                variant="outline"
                className="w-full text-sm py-1.5 px-3 text-jhu-accent-4 dark:text-jhu-accent-3 border-jhu-accent-4/70 dark:border-jhu-accent-3/70 hover:bg-jhu-accent-4/10 dark:hover:bg-jhu-accent-3/20"
                onClick={downloadAllHistoryCSV}
              >
                <Download className="mr-1.5 h-4 w-4" /> Download All History (CSV)
              </Button>
            </div>
          )}
        </aside>
      </div>

      <CodingSchemeEditor
        isOpen={isSchemeEditorOpen}
        onOpenChange={setIsSchemeEditorOpen}
        initialScheme={codingScheme}
        onSaveScheme={handleSaveSchemeInApp}
      />
      <AuthorInfoModal isOpen={isAuthorInfoModalOpen} onOpenChange={setIsAuthorInfoModalOpen} />
    </div>
  )
}
