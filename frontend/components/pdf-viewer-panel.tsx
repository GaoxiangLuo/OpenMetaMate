"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { PDFViewer, type PDFViewerRef, type PluginRegistry, type ScrollCapability, ZoomMode } from "@embedpdf/react-pdf-viewer"
import * as pdfjsLib from "pdfjs-dist"
import { FileWarning } from "lucide-react"
import type { Citation } from "@/lib/types"
import { extractLabelCandidates } from "@/lib/utils"

// Initialize pdfjs-dist worker for metadata extraction only (page labels)
if (typeof window !== "undefined" && !pdfjsLib.GlobalWorkerOptions.workerSrc) {
  const workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url)
  pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc.toString()
}

interface PdfViewerPanelProps {
  fileUrl?: string
  fileName?: string
  citations: Citation[]
  activeIndex: number
  footerHeight?: number
}

export default function PdfViewerPanel({
  fileUrl,
  fileName,
  citations,
  activeIndex,
  footerHeight,
}: PdfViewerPanelProps) {
  const [numPages, setNumPages] = useState<number>(0)
  const [pageLabels, setPageLabels] = useState<string[] | null>(null)
  const viewerRef = useRef<PDFViewerRef>(null)
  const scrollCapabilityRef = useRef<ScrollCapability | null>(null)
  const isMountedRef = useRef<boolean>(true)

  const safeIndex = citations.length > 0 ? Math.min(activeIndex, citations.length - 1) : 0
  const activeCitation = citations[safeIndex]

  // Track component mount status
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  // Reset state when fileUrl changes
  useEffect(() => {
    if (!fileUrl) {
      setNumPages(0)
      setPageLabels(null)
      scrollCapabilityRef.current = null
    } else {
      setPageLabels(null)
      scrollCapabilityRef.current = null
    }
  }, [fileUrl])

  // Extract page labels via pdfjs-dist (headless, no rendering)
  useEffect(() => {
    if (!fileUrl) return

    let cancelled = false

    const loadLabels = async () => {
      try {
        const pdf = await pdfjsLib.getDocument(fileUrl).promise
        if (cancelled || !isMountedRef.current) return

        const pages = pdf.numPages
        setNumPages(pages)

        const labels = await pdf.getPageLabels()
        if (cancelled || !isMountedRef.current) return

        if (Array.isArray(labels) && labels.length === pages) {
          setPageLabels(labels)
        } else {
          setPageLabels(null)
        }
      } catch (error) {
        if (!cancelled && isMountedRef.current) {
          console.warn("Failed to load page labels via pdfjs-dist", error)
          setPageLabels(null)
        }
      }
    }

    loadLabels()
    return () => {
      cancelled = true
    }
  }, [fileUrl])

  // Capture scroll capability when viewer is ready
  const handleViewerReady = useCallback((registry: PluginRegistry) => {
    const scrollPlugin = registry.getPlugin("scroll")
    if (scrollPlugin?.provides) {
      scrollCapabilityRef.current = scrollPlugin.provides() as ScrollCapability
    }
  }, [])

  // --- Page-label resolution logic (preserved from original implementation) ---

  const resolvedLabelLookup = useMemo(() => {
    if (!pageLabels || pageLabels.length === 0) {
      return new Map<number, number>()
    }

    const lookup = new Map<number, number>()
    pageLabels.forEach((label, index) => {
      const candidates = extractLabelCandidates(label)
      candidates.forEach((value) => {
        if (!lookup.has(value)) {
          lookup.set(value, index + 1)
        }
      })
    })
    return lookup
  }, [pageLabels])

  const numericOffset = useMemo(() => {
    if (!pageLabels || pageLabels.length === 0) {
      return null
    }

    for (let i = 0; i < pageLabels.length; i += 1) {
      const label = pageLabels[i]
      const candidates = extractLabelCandidates(label)
      const numericCandidate = candidates.find((candidate) => Number.isFinite(candidate))
      if (typeof numericCandidate === "number") {
        return i + 1 - numericCandidate
      }
    }

    return null
  }, [pageLabels])

  const citationOffsetPreference = useMemo(() => {
    if (citations.length === 0 || resolvedLabelLookup.size === 0) {
      return { offset: 0, ratio: 0 }
    }

    const histogram = new Map<number, number>()
    let matched = 0

    citations.forEach((citation) => {
      const raw = citation.pageNumber
      if (!raw || raw < 1) {
        return
      }

      const matchedPage = resolvedLabelLookup.get(raw)
      if (typeof matchedPage === "number") {
        const delta = matchedPage - raw
        histogram.set(delta, (histogram.get(delta) ?? 0) + 1)
        matched += 1
      }
    })

    if (matched === 0) {
      return { offset: 0, ratio: 0 }
    }

    let bestOffset = 0
    let bestCount = 0
    histogram.forEach((count, offset) => {
      if (count > bestCount) {
        bestOffset = offset
        bestCount = count
      }
    })

    return { offset: bestOffset, ratio: bestCount / matched }
  }, [citations, resolvedLabelLookup])

  const applyOffset = useMemo(() => {
    if (resolvedLabelLookup.size === 0) {
      return false
    }

    if (citationOffsetPreference.offset === 0) {
      return false
    }

    return citationOffsetPreference.ratio >= 0.6
  }, [citationOffsetPreference, resolvedLabelLookup])

  const resolvePageNumber = useCallback(
    (rawPage: number): number => {
      if (!rawPage || rawPage < 1) {
        return 1
      }

      let candidate = rawPage

      if (applyOffset) {
        const mapped = resolvedLabelLookup.get(rawPage)
        if (typeof mapped === "number") {
          candidate = mapped
        } else if (numericOffset !== null) {
          candidate = rawPage + numericOffset
        }
      }

      if (numPages > 0) {
        return Math.min(Math.max(candidate, 1), numPages)
      }

      return Math.max(candidate, 1)
    },
    [applyOffset, numericOffset, numPages, resolvedLabelLookup],
  )

  // --- Citation-driven navigation via scrollToPage ---

  useEffect(() => {
    if (citations.length === 0 || !activeCitation) return

    const targetPage = resolvePageNumber(activeCitation.pageNumber ?? 1)

    const navigate = () => {
      const scroll = scrollCapabilityRef.current
      if (scroll) {
        scroll.scrollToPage({ pageNumber: targetPage, behavior: "smooth" })
        return
      }

      // Retry if viewer isn't ready yet (e.g., on initial load with a pre-selected citation)
      const retryTimeout = setTimeout(() => {
        const retryScroll = scrollCapabilityRef.current
        if (retryScroll) {
          retryScroll.scrollToPage({ pageNumber: targetPage, behavior: "smooth" })
        }
      }, 1000)

      return retryTimeout
    }

    const timeout = navigate()
    return () => {
      if (timeout) clearTimeout(timeout)
    }
  }, [citations, activeCitation, resolvePageNumber])

  return (
    <section className="h-full flex-1 min-w-[360px] border-l border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-900 flex flex-col overflow-hidden">
      <header className="px-4 py-3 border-b border-slate-200 dark:border-slate-700/60 bg-slate-100/70 dark:bg-slate-800/60">
        <h2 className="text-sm font-semibold text-primary-jhuBlue dark:text-primary-jhuLightBlue">PDF Viewer</h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate" title={fileName}>
          {fileName || "Select a PDF to preview"}
        </p>
      </header>

      <div className="flex-1 overflow-hidden">
        {fileUrl ? (
          <PDFViewer
            ref={viewerRef}
            config={{
              src: fileUrl,
              theme: {
                preference: "light",
                light: {
                  background: { app: "#f1f5f9", surface: "#ffffff", surfaceAlt: "#f8fafc" },
                  accent: {
                    primary: "#002D72",
                    primaryHover: "#0077D8",
                    primaryActive: "#001a44",
                    primaryLight: "#e8f0fe",
                    primaryForeground: "#ffffff",
                  },
                  border: { default: "#e2e8f0", subtle: "#f1f5f9" },
                  scrollbar: { track: "#f1f5f9", thumb: "rgba(104,172,229,0.7)", thumbHover: "#68ACE5" },
                },
              },
              zoom: { defaultZoomLevel: ZoomMode.FitWidth },
              tabBar: "never",
              disabledCategories: [
                "annotation",
                "redaction",
                "document-export",
                "document-print",
                "capture",
                "history",
                "spread",
                "rotate",
              ],
            }}
            onReady={handleViewerReady}
            style={{ width: "100%", height: "100%" }}
          />
        ) : (
          <div className="flex flex-col items-center text-center gap-2 p-6 text-sm text-slate-600 dark:text-slate-300 h-full justify-center">
            <FileWarning className="h-6 w-6 text-slate-400" />
            <p>No PDF selected yet.</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-[260px]">
              Upload a document and choose a citation to jump to the relevant page.
            </p>
          </div>
        )}
      </div>

      <footer
        className="px-4 py-2.5 border-t-2 border-green-200 dark:border-green-800/60 bg-green-50 dark:bg-green-900/20 flex items-center"
        style={footerHeight ? { minHeight: footerHeight } : undefined}
      >
        <p className="text-[13px] font-medium text-slate-700 dark:text-slate-200">
          {"🌍🌲 "}
          <span className="font-semibold">Environmental Impact:</span> Each query uses ~0.34Wh and ~0.3ml water. Each
          PDF extraction may use 5-30x this amount depending on document size.{" "}
          <a
            href="https://blog.samaltman.com/the-gentle-singularity"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary-jhuBlue dark:text-primary-jhuLightBlue hover:underline font-medium"
          >
            [Source]
          </a>
        </p>
      </footer>
    </section>
  )
}
