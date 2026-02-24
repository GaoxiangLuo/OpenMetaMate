"use client"

import type React from "react"
import { useEffect, useRef, useState } from "react"

interface ResizablePanelContainerProps {
  left: React.ReactNode
  right: React.ReactNode
  initialLeftRatio?: number
  minLeftWidth?: number
  minRightWidth?: number
}

export default function ResizablePanelContainer({
  left,
  right,
  initialLeftRatio = 0.5,
  minLeftWidth = 360,
  minRightWidth = 360,
}: ResizablePanelContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [leftWidth, setLeftWidth] = useState<number | undefined>(undefined)
  const [isDragging, setIsDragging] = useState(false)

  useEffect(() => {
    if (typeof window === "undefined") return

    const updateWidth = () => {
      if (!containerRef.current) return
      const containerWidth = containerRef.current.offsetWidth
      const fallback = containerWidth * initialLeftRatio
      const base = typeof leftWidth === "number" ? leftWidth : fallback
      const clamped = Math.max(minLeftWidth, Math.min(containerWidth - minRightWidth, base))
      setLeftWidth(clamped)
    }

    updateWidth()
    window.addEventListener("resize", updateWidth)
    return () => window.removeEventListener("resize", updateWidth)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (event: MouseEvent) => {
      if (!containerRef.current) return
      const bounds = containerRef.current.getBoundingClientRect()
      const rawLeft = event.clientX - bounds.left
      const containerWidth = bounds.width
      const clampedLeft = Math.max(minLeftWidth, Math.min(containerWidth - minRightWidth, rawLeft))
      setLeftWidth(clampedLeft)
    }

    const stopDragging = () => setIsDragging(false)

    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", stopDragging)
    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", stopDragging)
    }
  }, [isDragging, minLeftWidth, minRightWidth])

  const startDragging = () => setIsDragging(true)

  return (
    <div ref={containerRef} className="flex flex-1 overflow-hidden">
      <div
        className="flex flex-col min-w-0"
        style={
          typeof leftWidth === "number"
            ? { width: leftWidth, flexBasis: leftWidth }
            : { width: `${initialLeftRatio * 100}%`, flexBasis: `${initialLeftRatio * 100}%` }
        }
      >
        {left}
      </div>
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize viewer"
        onMouseDown={startDragging}
        className={`w-1.5 cursor-col-resize bg-slate-200 dark:bg-slate-700/60 hover:bg-primary-jhuLightBlue/60 dark:hover:bg-primary-jhuBlue/60 transition-colors ${isDragging ? "bg-primary-jhuLightBlue dark:bg-primary-jhuBlue" : ""}`}
      />
      <div className="flex-1 min-w-0 flex flex-col">{right}</div>
    </div>
  )
}
