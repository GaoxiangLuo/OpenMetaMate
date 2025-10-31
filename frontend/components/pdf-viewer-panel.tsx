"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { pdfjs, Document, Page } from "react-pdf"
import type { PDFDocumentProxy } from "pdfjs-dist"
import { Button } from "@/components/ui/button"
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, FileWarning } from "lucide-react"
import type { Citation } from "@/lib/types"
import { extractLabelCandidates } from "@/lib/utils"

import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"

// Initialize PDF.js worker once per module load
if (typeof window !== "undefined" && !pdfjs.GlobalWorkerOptions.workerSrc) {
  const workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url)
  pdfjs.GlobalWorkerOptions.workerSrc = workerSrc.toString()
}

interface PdfViewerPanelProps {
  fileUrl?: string
  fileName?: string
  citations: Citation[]
  activeIndex: number
}

const ZOOM_STEP = 0.2
const MIN_ZOOM = 0.5
const MAX_ZOOM = 2.4

export default function PdfViewerPanel({ fileUrl, fileName, citations, activeIndex }: PdfViewerPanelProps) {
  const [numPages, setNumPages] = useState<number>(0)
  const [pageNumber, setPageNumber] = useState<number>(1)
  const [zoomMultiplier, setZoomMultiplier] = useState<number>(1)
  const [pageLabels, setPageLabels] = useState<string[] | null>(null)
  const viewerContainerRef = useRef<HTMLDivElement>(null)
  const isMountedRef = useRef<boolean>(true)

  const safeIndex = citations.length > 0 ? Math.min(activeIndex, citations.length - 1) : 0
  const activeCitation = citations[safeIndex]

  // Cleanup effect to track component mount status
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  useEffect(() => {
    if (!fileUrl) {
      setNumPages(0)
      setPageNumber(1)
      setZoomMultiplier(1)
      setPageLabels(null)
    } else {
      setPageNumber(1)
      setZoomMultiplier(1)
    }
  }, [fileUrl])

  const changePage = useCallback(
    (offset: number) => {
      setPageNumber((prev) => {
        if (!fileUrl || numPages === 0) {
          return 1
        }

        const next = prev + offset
        if (next < 1) return 1
        if (numPages && next > numPages) return numPages
        return next
      })
    },
    [fileUrl, numPages],
  )

  const handlePageRenderError = (error: Error) => {
    const message = (error?.message || "").toLowerCase()
    if (error?.name === "AbortError" || message.includes("cancel")) {
      return
    }
    console.error("Failed to render PDF page", error)
  }

  const increaseZoom = () => {
    setZoomMultiplier((prev) => Math.min(MAX_ZOOM, prev + ZOOM_STEP))
  }

  const decreaseZoom = () => {
    setZoomMultiplier((prev) => Math.max(MIN_ZOOM, prev - ZOOM_STEP))
  }

  // Simple scale calculation - just use zoom multiplier directly
  const effectiveScale = zoomMultiplier

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

  useEffect(() => {
    if (citations.length > 0 && activeCitation) {
      setPageNumber(resolvePageNumber(activeCitation.pageNumber ?? 1))
    } else {
      setPageNumber(1)
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

      <div className="flex-1 flex flex-col">
        <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-slate-700 bg-slate-100/60 dark:bg-slate-800/60 text-sm text-slate-600 dark:text-slate-300">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => changePage(-1)}
              disabled={!fileUrl || numPages <= 1 || pageNumber <= 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span>
              Page {pageNumber}
              {numPages > 0 ? ` / ${numPages}` : ""}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => changePage(1)}
              disabled={!fileUrl || numPages === 0 || pageNumber >= numPages}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={decreaseZoom}
              disabled={zoomMultiplier <= MIN_ZOOM}
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span>{Math.round(zoomMultiplier * 100)}%</span>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={increaseZoom}
              disabled={zoomMultiplier >= MAX_ZOOM}
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div
          ref={viewerContainerRef}
          className="flex-1 overflow-auto bg-slate-100 dark:bg-slate-900 flex justify-center items-start p-4"
        >
          {fileUrl ? (
            <Document
              file={fileUrl}
              loading={<div className="flex items-center justify-center p-8 text-slate-500">Loading PDF...</div>}
              error={<div className="flex items-center justify-center p-8 text-red-500">Failed to load PDF</div>}
              onLoadSuccess={(pdf: PDFDocumentProxy) => {
                const pages = pdf.numPages
                setNumPages(pages)
                setPageNumber((current) => {
                  if (pages <= 0) return 1
                  const clamped = Math.min(Math.max(current, 1), pages)
                  return clamped
                })

                pdf
                  .getPageLabels()
                  .then((labels: string[] | null) => {
                    // Only update state if component is still mounted
                    if (!isMountedRef.current) return

                    if (Array.isArray(labels) && labels.length === pages) {
                      setPageLabels(labels)
                    } else {
                      setPageLabels(null)
                    }
                  })
                  .catch((error: Error) => {
                    // Only update state if component is still mounted
                    if (!isMountedRef.current) return

                    console.warn("Failed to load page labels", error)
                    setPageLabels(null)
                  })
              }}
              onLoadError={(error: Error) => console.error("Failed to load PDF", error)}
            >
              <Page
                pageNumber={pageNumber}
                scale={effectiveScale}
                renderAnnotationLayer={false}
                renderTextLayer={false}
                onRenderError={handlePageRenderError}
                onLoadSuccess={() => {
                  // Page loaded successfully
                }}
              />
            </Document>
          ) : (
            <div className="flex flex-col items-center text-center gap-2 p-6 text-sm text-slate-600 dark:text-slate-300">
              <FileWarning className="h-6 w-6 text-slate-400" />
              <p>No PDF selected yet.</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 max-w-[260px]">
                Upload a document and choose a citation to jump to the relevant page.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
