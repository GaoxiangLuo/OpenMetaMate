"use client"

import { useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Copy, ExternalLink, Coffee, Heart, Leaf } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

interface AuthorInfoModalProps {
  isOpen: boolean
  onOpenChange: (isOpen: boolean) => void
  scrollToMindful?: boolean
}

const citations = {
  bibtex: `@misc{wang_luo_2024,
    title={MetaMate: Large Language Model to the Rescue of Automated Data Extraction for Educational Systematic Reviews and Meta-analyses},
    url={osf.io/preprints/edarxiv/wn3cd},
    DOI={10.35542/osf.io/wn3cd},
    publisher={EdArXiv},
    author={Wang, Xue and Luo, Gaoxiang},
    year={2024},
    month={May}
}`,
  apa: `Wang, X., & Luo, G. (2024). MetaMate: Large language model to the rescue of automated data extraction for educational systematic reviews and meta-analyses. https://doi.org/10.35542/osf.io/wn3cd`,
  mla: `Wang, Xue, and Gaoxiang Luo. "Metamate: Large Language Model to the Rescue of Automated Data Extraction for Educational Systematic Reviews and Meta-analyses." EdArXiv, 2 May 2024. Web.`,
}

export default function AuthorInfoModal({ isOpen, onOpenChange, scrollToMindful }: AuthorInfoModalProps) {
  const { toast } = useToast()
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const mindfulRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!isOpen) return
    // Wait for the dialog and ScrollArea to fully render
    const raf = requestAnimationFrame(() => {
      const viewport = scrollAreaRef.current?.querySelector("[data-radix-scroll-area-viewport]")
      if (!viewport) return
      if (scrollToMindful && mindfulRef.current) {
        viewport.scrollTop = mindfulRef.current.offsetTop
      } else {
        viewport.scrollTop = 0
      }
    })
    return () => cancelAnimationFrame(raf)
  }, [isOpen, scrollToMindful])

  const copyToClipboard = (text: string, format: string) => {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        toast({
          title: "Copied to Clipboard!",
          description: `${format} citation copied.`,
          variant: "default",
          className: "bg-jhu-accent-4 text-white dark:bg-jhu-accent-3 dark:text-slate-900",
        })
      })
      .catch((err) => {
        toast({
          title: "Copy Failed",
          description: "Could not copy text. Please try manually.",
          variant: "destructive",
        })
        console.error("Failed to copy: ", err)
      })
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl bg-white dark:bg-slate-900 border-primary-jhuBlue shadow-xl">
        <DialogHeader className="pb-4 border-b border-slate-200 dark:border-slate-700">
          <DialogTitle className="text-xl font-semibold text-primary-jhuBlue dark:text-primary-jhuLightBlue">
            About MetaMate & Citations
          </DialogTitle>
        </DialogHeader>

        <ScrollArea ref={scrollAreaRef} className="max-h-[65vh] p-1 pr-4 mt-2">
          <div className="space-y-6 py-4">
            <section>
              <div className="text-center mb-4">
                <h4 className="text-base font-medium text-slate-700 dark:text-slate-300 mb-2">
                  MetaMate: Large Language Model to the Rescue of Automated Data Extraction for Educational Systematic
                  Reviews and Meta-analyses
                </h4>
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                  <a
                    href="https://xwang297.github.io/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary-jhuBlue hover:text-primary-jhuLightBlue dark:text-primary-jhuLightBlue dark:hover:text-primary-jhuBlue"
                  >
                    Xue Wang<sup>*,1</sup>
                  </a>
                  ,
                  <a
                    href="https://gaoxiangluo.github.io/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-1 font-medium text-primary-jhuBlue hover:text-primary-jhuLightBlue dark:text-primary-jhuLightBlue dark:hover:text-primary-jhuBlue"
                  >
                    Gaoxiang Luo<sup>*,2</sup>
                  </a>
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-500">
                  <sup>1</sup>Johns Hopkins University, <sup>2</sup>University of Minnesota, Twin Cities
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-500 italic mb-3">*Equal contribution</p>
                <div className="flex justify-center gap-4">
                  <a
                    href="https://doi.org/10.35542/osf.io/wn3cd"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-sm text-jhu-blue hover:text-jhu-light-blue dark:text-jhu-light-blue dark:hover:text-jhu-blue transition-colors"
                  >
                    EdArXiv <ExternalLink className="h-3 w-3" />
                  </a>
                  <a
                    href="https://github.com/xwang297/metamate-dataset"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-sm text-jhu-blue hover:text-jhu-light-blue dark:text-jhu-light-blue dark:hover:text-jhu-blue transition-colors"
                  >
                    Dataset <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </section>

            <section>
              <h3 className="text-lg font-semibold mb-3 text-primary-jhuBlue dark:text-primary-jhuLightBlue">
                📢 News & Updates
              </h3>
              <div className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[02/2026]</span>
                  <span>
                    Based on insights from our user study, we redesigned much of the MetaMate experience: a new embedded
                    PDF viewer, a collapsible extraction history panel, granular real-time progress feedback, a revamped
                    coding scheme editor with guided workflows and unsaved-changes protection, richer codebook support
                    including hierarchical schemes and full Unicode rendering in exports.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[02/2026]</span>
                  <span>
                    Our user study paper{" "}
                    <em>
                      &quot;MetaMate: Understanding How Educational Researchers Experience AI-Assisted Data Extraction
                      for Systematic Reviews&quot;
                    </em>{" "}
                    has been accepted to the{" "}
                    <strong>2026 CHI Conference on Human Factors in Computing Systems (Poster)</strong>.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[11/2025]</span>
                  <span>
                    <strong>Enhanced extraction for tables and figures</strong> is now available! Enable it via the
                    Settings (⚙️) to get better extraction of complex tables, mathematical equations, and infographic
                    figures. Plus, it works for scanned PDFs as well.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[09/2025]</span>
                  <span>
                    Shipped the two most-requested upgrades: <strong>grounded PDF navigation</strong> that jumps
                    directly to cited pages and <strong>manual answer corrections</strong> that flow into CSV exports.
                    Explore these enhancements in your next review!
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[09/2025]</span>
                  <span>
                    Thanks to{" "}
                    <a
                      href="https://www.thesynthesis.company/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      Synthesis Company
                    </a>{" "}
                    (YC S24) for supporting our server hosting for 2025-2026.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[06/2025]</span>
                  <span>
                    MetaMate 2.0 will appear on the Society for Research on Educational Effectiveness (
                    <strong>SREE</strong>) 2025 conference in Chicago IL, USA on Octorber 8-11, 2025. We will highlight
                    our new results on a large-scale public meta-analysis dataset, and models of various sizes including
                    ones that can be hosted locally with a laptop.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[11/2024]</span>
                  <span>
                    MetaMate 1.0 will appear on the American Educational Research Association (<strong>AERA</strong>)
                    2025 Annual Meeting in Denver CO, USA on April 25, 2025.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[08/2024]</span>
                  <span>
                    MetaMate is now in Beta and completely free for everyone to use—explore, enjoy, and share your
                    feedback to help us improve!
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[07/2024]</span>
                  <span>
                    MetaMate has been accepted to <strong>OpenAI&apos;s Researcher Access Program</strong>.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[06/2024]</span>
                  <span>
                    MetaMate (PoC) will appear on the Society for Research on Educational Effectiveness (
                    <strong>SREE</strong>) 2024 conference in Baltimore MD, USA on September 18-21, 2024.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[05/2024]</span>
                  <span>
                    MetaMate is now available on{" "}
                    <a
                      href="https://doi.org/10.35542/osf.io/wn3cd"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      EdArXiv
                    </a>
                    .
                  </span>
                </div>
              </div>
            </section>

            <section>
              <h3 className="text-lg font-semibold mb-3 text-primary-jhuBlue dark:text-primary-jhuLightBlue">
                ⚙️ Ongoing Work & Roadmap
              </h3>
              <div className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
                <div className="flex items-start gap-2">
                  <span className="text-green-600 dark:text-green-400 mt-0.5">✓</span>
                  <span>
                    <strong>Customization:</strong> allow users to customize the coding scheme for data extraction.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-green-600 dark:text-green-400 mt-0.5">✓</span>
                  <span>
                    <strong>Trustworthiness:</strong> include a confidence score for each extracted data element.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-green-600 dark:text-green-400 mt-0.5">✓</span>
                  <span>
                    <strong>PDF Viewer:</strong> clicking on a coding result will jump to the corresponding page.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-green-600 dark:text-green-400 mt-0.5">✓</span>
                  <span>
                    <strong>Citations:</strong> differentiate between direct evidence and high-level inference.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-green-600 dark:text-green-400 mt-0.5">✓</span>
                  <span>
                    <strong>Manual Correction:</strong> allow users to edit coding results before exporting.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-green-600 dark:text-green-400 mt-0.5">✓</span>
                  <span>
                    <strong>Enhanced Table/Figure Understanding:</strong> add Vision Language Model (VLM)/Optical
                    Character Recognition (OCR)/TableFormer integration (e.g., MinerU 2.5, DeepSeek OCR, MathPix, etc.)
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-slate-400 dark:text-slate-500 mt-0.5">☐</span>
                  <span>
                    <strong>Enhanced Confidence:</strong> add self-consistency sampling for monte-carlo estimation with
                    cached input tokens.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-slate-400 dark:text-slate-500 mt-0.5">☐</span>
                  <span>
                    <strong>Multi-Agent:</strong> incorporate multi LLM agents as multi coders for debate.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-slate-400 dark:text-slate-500 mt-0.5">☐</span>
                  <span>
                    <strong>Description Optimization:</strong> automate description completions in coding schemes with
                    LLM as an optimizer and Bayesian optimization.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-slate-400 dark:text-slate-500 mt-0.5">☐</span>
                  <span>
                    <strong>Reinforcement Learning:</strong> finetune a specialized small base LLM for educational
                    context extraction with proper reward functions.
                  </span>
                </div>
              </div>
            </section>

            <section>
              <h3 className="text-lg font-semibold mb-3 text-primary-jhuBlue dark:text-primary-jhuLightBlue">
                How to Cite MetaMate
              </h3>
              <Tabs defaultValue="apa" className="w-full">
                <TabsList className="grid w-full grid-cols-3 bg-slate-100 dark:bg-slate-800">
                  <TabsTrigger
                    value="apa"
                    className="data-[state=active]:bg-primary-jhuBlue data-[state=active]:text-white dark:data-[state=active]:bg-primary-jhuLightBlue dark:data-[state=active]:text-primary-jhuBlue"
                  >
                    APA
                  </TabsTrigger>
                  <TabsTrigger
                    value="mla"
                    className="data-[state=active]:bg-primary-jhuBlue data-[state=active]:text-white dark:data-[state=active]:bg-primary-jhuLightBlue dark:data-[state=active]:text-primary-jhuBlue"
                  >
                    MLA
                  </TabsTrigger>
                  <TabsTrigger
                    value="bibtex"
                    className="data-[state=active]:bg-primary-jhuBlue data-[state=active]:text-white dark:data-[state=active]:bg-primary-jhuLightBlue dark:data-[state=active]:text-primary-jhuBlue"
                  >
                    BibTeX
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="apa" className="mt-3">
                  <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-md border border-slate-200 dark:border-slate-700">
                    <pre className="citation-text text-xs whitespace-pre-wrap break-all text-slate-700 dark:text-slate-300 select-all">
                      {citations.apa}
                    </pre>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => copyToClipboard(citations.apa, "APA")}
                      className="mt-2 text-xs text-jhu-accent-1 border-jhu-accent-1 hover:bg-jhu-accent-1/10"
                    >
                      <Copy className="mr-1.5 h-3 w-3" /> Copy APA
                    </Button>
                  </div>
                </TabsContent>
                <TabsContent value="mla" className="mt-3">
                  <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-md border border-slate-200 dark:border-slate-700">
                    <pre className="citation-text text-xs whitespace-pre-wrap break-all text-slate-700 dark:text-slate-300 select-all">
                      {citations.mla}
                    </pre>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => copyToClipboard(citations.mla, "MLA")}
                      className="mt-2 text-xs text-jhu-accent-1 border-jhu-accent-1 hover:bg-jhu-accent-1/10"
                    >
                      <Copy className="mr-1.5 h-3 w-3" /> Copy MLA
                    </Button>
                  </div>
                </TabsContent>
                <TabsContent value="bibtex" className="mt-3">
                  <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-md border border-slate-200 dark:border-slate-700">
                    <pre className="citation-text text-xs whitespace-pre-wrap break-all text-slate-700 dark:text-slate-300 select-all">
                      {citations.bibtex}
                    </pre>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => copyToClipboard(citations.bibtex, "BibTeX")}
                      className="mt-2 text-xs text-jhu-accent-1 border-jhu-accent-1 hover:bg-jhu-accent-1/10"
                    >
                      <Copy className="mr-1.5 h-3 w-3" /> Copy BibTeX
                    </Button>
                  </div>
                </TabsContent>
              </Tabs>
            </section>

            <section>
              <h3 className="text-lg font-semibold mb-3 text-primary-jhuBlue dark:text-primary-jhuLightBlue flex items-center gap-2">
                <Heart className="h-5 w-5 text-red-500" />
                Supported by Synthesis Company
              </h3>
              <div className="text-sm text-slate-700 dark:text-slate-300 mb-3">
                <p className="mb-2">
                  We&apos;re grateful to{" "}
                  <a
                    href="https://www.thesynthesis.company/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 dark:text-blue-400 hover:underline font-medium"
                  >
                    Synthesis Company
                  </a>{" "}
                  (YC S24) for supporting our server hosting for 2025-2026, enabling us to keep MetaMate free and
                  accessible to researchers worldwide.
                </p>
              </div>
            </section>

            <section ref={mindfulRef}>
              <h3 className="text-lg font-semibold mb-3 text-primary-jhuBlue dark:text-primary-jhuLightBlue flex items-center gap-2">
                <Leaf className="h-5 w-5 text-green-600" />
                Using MetaMate Mindfully
              </h3>
              <div className="space-y-3 text-sm text-slate-700 dark:text-slate-300">
                <div>
                  <h4 className="font-semibold text-slate-800 dark:text-slate-200 mb-1">Why this matters to us</h4>
                  <p>
                    We built MetaMate because we believe AI can meaningfully support educational researchers. But we
                    also want to be honest about the resources AI tools consume.
                  </p>
                  <p className="mt-2">
                    In the summer of 2025, during a professional event, I (Xue Wang) met a fellow PhD student — a mother
                    of two from a Texas community near newly constructed data centers. She shared that her community was
                    experiencing water shortages that were affecting her family&apos;s daily life. That conversation
                    stayed with us. The environmental costs of AI are not abstract — they affect real communities and
                    real families, including the next generation we study and serve as educational researchers.
                  </p>
                  <p className="mt-2">
                    Every query to MetaMate uses approximately 0.34 watt-hours of energy and about one-fifteenth of a
                    teaspoon of water. An extraction task uses roughly 5 to 30 times that amount, depending on text
                    length. Individually, these numbers are small. Collectively, across thousands of queries, they are
                    not.
                  </p>
                  <p className="mt-2">
                    This is not a reason to stop using AI. It is a reason to use it thoughtfully. The good news is that
                    the practices that reduce environmental cost are the same ones that give you better, faster results.
                  </p>
                </div>
                <div>
                  <h4 className="font-semibold text-slate-800 dark:text-slate-200 mb-1">
                    Three tips for smarter, greener extractions
                  </h4>
                  <ol className="list-decimal list-outside ml-5 space-y-2">
                    <li>
                      <strong>Maximize each query — extract everything at once.</strong> Develop a complete codebook
                      before you begin. Rather than extracting a few data elements, then coming back later to extract
                      more from the same articles, define all the data elements you need upfront. This avoids redundant
                      uploads and repeated processing of the same documents.
                    </li>
                    <li>
                      <strong>Test before you scale — pilot first, then batch.</strong> Your first codebook may not
                      extract exactly what you expect. Run your complete codebook on a small set of articles first,
                      review the results, and revise your definitions. Once you&apos;re confident, upload your full set
                      of articles for extraction. This saves both your time and computational resources.
                    </li>
                    <li>
                      <strong>Save your work after each session.</strong> Because MetaMate doesn&apos;t require a login,
                      your extracted data is not stored between sessions. Before closing the page, download your coded
                      data as a CSV file using the button at the bottom right of the extraction page. This simple step
                      means you won&apos;t need to re-upload and re-process the same articles — saving your effort and
                      reducing unnecessary computation.
                    </li>
                  </ol>
                </div>
              </div>
            </section>

            <section>
              <h3 className="text-lg font-semibold mb-3 text-primary-jhuBlue dark:text-primary-jhuLightBlue flex items-center gap-2">
                <Coffee className="h-5 w-5 text-amber-600" />
                Support MetaMate
              </h3>
              <div className="text-sm text-slate-700 dark:text-slate-300 mb-3">
                <p className="mb-2">
                  MetaMate is developed and maintained by PhD students. If you find this tool helpful for your research,
                  consider citing our work or buying us a coffee.
                </p>
              </div>
              <Button
                variant="outline"
                onClick={() => window.open("https://buymeacoffee.com/metamate", "_blank")}
                className="text-sm text-amber-700 border-amber-600/70 hover:bg-amber-100 dark:text-amber-500 dark:border-amber-500/70 dark:hover:bg-amber-900/20"
              >
                <Coffee className="mr-1.5 h-4 w-4" /> Buy Us a Coffee
              </Button>
            </section>

            <div className="text-center pt-6 mt-6 border-t border-slate-200 dark:border-slate-700">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Developed at University of Minnesota and Johns Hopkins University
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">© 2024-2026 MetaMate Authors</p>
            </div>
          </div>
        </ScrollArea>

        <DialogFooter className="pt-4 border-t border-slate-200 dark:border-slate-700">
          <DialogClose asChild>
            <Button
              variant="outline"
              className="border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              Close
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
