"use client"

import type React from "react"

import { useState, useEffect, useRef, useCallback } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import { PlusCircle, Trash2, Save, Info, Upload, DownloadIcon } from "lucide-react" // Renamed Download to DownloadIcon
import type { CodingSchemeItem } from "@/lib/types"
import { useToast } from "@/hooks/use-toast"

interface CodingSchemeEditorProps {
  isOpen: boolean
  onOpenChange: (isOpen: boolean) => void
  initialScheme: CodingSchemeItem[]
  onSaveScheme: (updatedScheme: CodingSchemeItem[]) => void // Renamed for clarity
}

export default function CodingSchemeEditor({
  isOpen,
  onOpenChange,
  initialScheme,
  onSaveScheme,
}: CodingSchemeEditorProps) {
  const [scheme, setScheme] = useState<CodingSchemeItem[]>(initialScheme)
  const [showUnsavedWarning, setShowUnsavedWarning] = useState(false)
  const fileUploadRef = useRef<HTMLInputElement>(null)
  const { toast } = useToast()

  useEffect(() => {
    // Deep copy to avoid mutating the prop directly
    setScheme(JSON.parse(JSON.stringify(initialScheme)))
  }, [initialScheme, isOpen])

  const hasUnsavedChanges = useCallback(() => {
    if (scheme.length !== initialScheme.length) return true
    return scheme.some((item, index) => {
      const original = initialScheme[index]
      return (
        item.id !== original.id ||
        item.name !== original.name ||
        item.dataType !== original.dataType ||
        item.description !== original.description ||
        item.includeInExtraction !== original.includeInExtraction
      )
    })
  }, [scheme, initialScheme])

  const handleDialogOpenChange = (open: boolean) => {
    if (!open && hasUnsavedChanges()) {
      setShowUnsavedWarning(true)
      return
    }
    onOpenChange(open)
  }

  const handleConfirmDiscard = () => {
    setShowUnsavedWarning(false)
    // Delay closing the main dialog so the AlertDialog overlay fully unmounts first,
    // otherwise Radix leaves pointer-events:none on the body.
    requestAnimationFrame(() => {
      onOpenChange(false)
    })
  }

  const handleAddItem = () => {
    setScheme([
      ...scheme,
      {
        id: Date.now().toString() + Math.random().toString(36).substring(2, 7), // More unique ID
        name: "",
        dataType: "Text",
        description: "",
        includeInExtraction: true, // Default to true
      },
    ])
  }

  const handleRemoveItem = (id: string) => {
    setScheme(scheme.filter((item) => item.id !== id))
  }

  const handleItemChange = (id: string, field: keyof CodingSchemeItem, value: string | boolean) => {
    setScheme(scheme.map((item) => (item.id === id ? { ...item, [field]: value } : item)))
  }

  const handleDataTypeChange = (id: string, value: CodingSchemeItem["dataType"]) => {
    setScheme(scheme.map((item) => (item.id === id ? { ...item, dataType: value } : item)))
  }

  const handleSaveChangesToApp = () => {
    onSaveScheme(JSON.parse(JSON.stringify(scheme))) // Pass a deep copy
    toast({ title: "Scheme Applied", description: "Coding scheme changes have been applied to the current session." })
    onOpenChange(false) // Close the dialog after applying the scheme
  }

  const handleDownloadScheme = () => {
    if (scheme.length === 0) {
      toast({ title: "Empty Scheme", description: "Cannot download an empty coding scheme.", variant: "destructive" })
      return
    }
    const jsonString = JSON.stringify(scheme, null, 2)
    const blob = new Blob([jsonString], { type: "application/json" })
    const href = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = href
    link.download = `MetaMate_CodingScheme_${new Date().toISOString().split("T")[0]}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(href)
    toast({ title: "Scheme Downloaded", description: "Coding scheme saved to your computer." })
  }

  const handleUploadSchemeFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const content = e.target?.result
          if (typeof content === "string") {
            const uploadedScheme = JSON.parse(content) as CodingSchemeItem[]
            // Basic validation (can be more thorough)
            if (
              Array.isArray(uploadedScheme) &&
              uploadedScheme.every(
                (item) => item.id && item.name && item.dataType && typeof item.includeInExtraction === "boolean",
              )
            ) {
              setScheme(uploadedScheme) // Update editor state
              onSaveScheme(JSON.parse(JSON.stringify(uploadedScheme))) // Apply to app state
              toast({ title: "Scheme Uploaded", description: "Coding scheme loaded and applied." })
            } else {
              throw new Error("Invalid scheme file format.")
            }
          }
        } catch (error) {
          console.error("Failed to upload scheme:", error)
          toast({
            title: "Upload Failed",
            description: (error as Error).message || "Invalid JSON file or scheme structure.",
            variant: "destructive",
          })
        }
      }
      reader.readAsText(file)
    }
    event.target.value = "" // Reset file input
  }

  return (
    <>
    <Dialog open={isOpen} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="sm:max-w-[700px] md:max-w-[850px] bg-white dark:bg-slate-900 border-primary-jhuBlue shadow-xl">
        <DialogHeader className="pb-4 border-b border-slate-200 dark:border-slate-700">
          <DialogTitle className="text-xl font-semibold text-primary-jhuBlue dark:text-primary-jhuLightBlue">
            Edit Study Coding Scheme
          </DialogTitle>
          <DialogDescription className="text-sm text-slate-500 dark:text-slate-400 flex items-start gap-2 mt-2 p-2 bg-jhu-light-blue/10 rounded-md border border-jhu-light-blue/30">
            <Info className="h-4 w-4 mt-0.5 text-jhu-light-blue shrink-0" />
            <span>
              Use a forward slash{" "}
              <code className="font-mono bg-slate-200 dark:bg-slate-700 px-1 py-0.5 rounded text-xs">/</code> in the
              &apos;Name&apos; field to indicate hierarchy (e.g., &quot;Demographics/Age&quot;). You can{" "}
              <strong>Download</strong> your scheme to save it for later, or <strong>Upload</strong> a previously saved
              scheme to quickly restore it across sessions.
            </span>
          </DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-2 mt-2 mb-1 px-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fileUploadRef.current?.click()}
            className="text-xs text-jhu-accent-4 border-jhu-accent-4 hover:bg-jhu-accent-4/10"
          >
            <Upload className="mr-1.5 h-3.5 w-3.5" /> Upload Scheme
          </Button>
          <input type="file" accept=".json" ref={fileUploadRef} onChange={handleUploadSchemeFile} className="hidden" />
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadScheme}
            className="text-xs text-jhu-accent-1 border-jhu-accent-1 hover:bg-jhu-accent-1/10"
          >
            <DownloadIcon className="mr-1.5 h-3.5 w-3.5" /> Download Scheme
          </Button>
        </div>
        <ScrollArea className="max-h-[55vh] p-1 pr-4">
          <div className="space-y-4 py-4">
            {scheme.map((item, index) => (
              <div
                key={item.id}
                className="p-3 border border-slate-300 dark:border-slate-700 rounded-md space-y-3 bg-slate-50 dark:bg-slate-800/30 shadow-subtle"
              >
                <div className="flex justify-between items-center">
                  <h4 className="font-semibold text-base text-primary-jhuBlue dark:text-primary-jhuLightBlue">
                    Item {index + 1}
                  </h4>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveItem(item.id)}
                    aria-label="Remove item"
                    className="text-red-500 hover:bg-red-500/10 h-7 w-7"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor={`name-${item.id}`} className="text-xs text-slate-600 dark:text-slate-400">
                      Name
                    </Label>
                    <Input
                      id={`name-${item.id}`}
                      value={item.name}
                      onChange={(e) => handleItemChange(item.id, "name", e.target.value)}
                      placeholder="e.g., Study Title, Demographics/Age"
                      className="text-sm border-slate-300 dark:border-slate-600 focus:border-primary-jhuLightBlue dark:focus:border-primary-jhuLightBlue"
                    />
                  </div>
                  <div>
                    <Label htmlFor={`dataType-${item.id}`} className="text-xs text-slate-600 dark:text-slate-400">
                      Data Type
                    </Label>
                    <Select
                      value={item.dataType}
                      onValueChange={(value: CodingSchemeItem["dataType"]) => handleDataTypeChange(item.id, value)}
                    >
                      <SelectTrigger
                        id={`dataType-${item.id}`}
                        className="text-sm border-slate-300 dark:border-slate-600 focus:border-primary-jhuLightBlue dark:focus:border-primary-jhuLightBlue"
                      >
                        <SelectValue placeholder="Select data type" />
                      </SelectTrigger>
                      <SelectContent className="bg-white dark:bg-slate-800 border-slate-300 dark:border-slate-600">
                        <SelectItem value="Text">Text</SelectItem>
                        <SelectItem value="Numeric">Numeric</SelectItem>
                        <SelectItem value="Boolean">Boolean</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label htmlFor={`description-${item.id}`} className="text-xs text-slate-600 dark:text-slate-400">
                    Description
                  </Label>
                  <Textarea
                    id={`description-${item.id}`}
                    value={item.description}
                    onChange={(e) => handleItemChange(item.id, "description", e.target.value)}
                    placeholder="Briefly describe this data element"
                    rows={3}
                    className="text-sm border-slate-300 dark:border-slate-600 focus:border-primary-jhuLightBlue dark:focus:border-primary-jhuLightBlue min-h-[90px]"
                  />
                </div>
                <div className="flex items-center space-x-2 pt-1">
                  <Checkbox
                    id={`include-${item.id}`}
                    checked={item.includeInExtraction}
                    onCheckedChange={(checked) => handleItemChange(item.id, "includeInExtraction", !!checked)}
                    className="border-primary-jhuBlue data-[state=checked]:bg-primary-jhuBlue data-[state=checked]:text-white dark:border-primary-jhuLightBlue dark:data-[state=checked]:bg-primary-jhuLightBlue dark:data-[state=checked]:text-primary-jhuBlue"
                  />
                  <Label
                    htmlFor={`include-${item.id}`}
                    className="text-xs font-medium text-slate-700 dark:text-slate-300 cursor-pointer"
                  >
                    Include this item in current extraction
                  </Label>
                </div>
              </div>
            ))}
            <Button
              variant="outline"
              onClick={handleAddItem}
              className="w-full mt-4 border-jhu-accent-4 text-jhu-accent-4 hover:bg-jhu-accent-4/10 dark:text-jhu-accent-3 dark:border-jhu-accent-3 dark:hover:bg-jhu-accent-3/20"
            >
              <PlusCircle className="mr-2 h-4 w-4" /> Add Item
            </Button>
          </div>
        </ScrollArea>
        <DialogFooter className="pt-4 border-t border-slate-200 dark:border-slate-700">
          <Button
            variant="outline"
            onClick={() => handleDialogOpenChange(false)}
            className="border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSaveChangesToApp}
            className="bg-primary-jhuBlue hover:bg-primary-jhuBlue/90 text-white dark:bg-primary-jhuLightBlue dark:text-primary-jhuBlue dark:hover:bg-primary-jhuLightBlue/90"
          >
            <Save className="mr-2 h-4 w-4" /> Apply Scheme to Session
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    <AlertDialog open={showUnsavedWarning} onOpenChange={setShowUnsavedWarning}>
      <AlertDialogContent className="bg-white dark:bg-slate-900 border-primary-jhuBlue">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-primary-jhuBlue dark:text-primary-jhuLightBlue">
            Unsaved Changes
          </AlertDialogTitle>
          <AlertDialogDescription>
            You have unsaved changes to the coding scheme. If you close without applying, your changes will be lost.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel className="border-slate-300 dark:border-slate-600">
            Keep Editing
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirmDiscard}
            className="bg-red-600 hover:bg-red-700 text-white"
          >
            Discard Changes
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  )
}
