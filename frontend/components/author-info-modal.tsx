"use client"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Copy, ExternalLink, Coffee } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

interface AuthorInfoModalProps {
  isOpen: boolean
  onOpenChange: (isOpen: boolean) => void
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

export default function AuthorInfoModal({ isOpen, onOpenChange }: AuthorInfoModalProps) {
  const { toast } = useToast()

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

        <ScrollArea className="max-h-[65vh] p-1 pr-4 mt-2">
          <div className="space-y-6 py-4">
            <section>
              <div className="text-center mb-4">
                <h4 className="text-base font-medium text-slate-700 dark:text-slate-300 mb-2">
                  MetaMate: Large Language Model to the Rescue of Automated Data Extraction for Educational Systematic
                  Reviews and Meta-analyses
                </h4>
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                  <span className="font-medium">Xue Wang¹</span>, <span className="font-medium">Gaoxiang Luo²</span>
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-500 mb-3">
                  ¹Johns Hopkins University, ²University of Minnesota, Twin Cities
                </p>
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
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[06/2025]</span>
                  <span>
                    MetaMate 2.0 will appear on the Society for Research on Educational Effectiveness (SREE) 2025
                    conference in Chicago IL, USA on Octorber 8-11, 2025. We will highlight our new results on a
                    large-scale public meta-analysis dataset, and various model choices including ones that can be
                    hosted locally with a laptop.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[11/2024]</span>
                  <span>
                    MetaMate 1.0 will appear on the American Educational Research Association (AERA) 2025 Annual Meeting
                    in Denver CO, USA on April 25, 2025.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[08/2024]</span>
                  <span>
                    MetaMate is now in Beta and completely free for everyone to use—explore, enjoy, and share your
                    feedback to help us improve!{" "}
                    <a href="/support" target="_blank" className="text-jhu-blue hover:underline">
                      Support our work
                    </a>{" "}
                    to keep it free.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[07/2024]</span>
                  <span>MetaMate has been accepted to OpenAI&apos;s Researcher Access Program.</span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[06/2024]</span>
                  <span>
                    MetaMate (PoC) will appear on the Society for Research on Educational Effectiveness (SREE) 2024
                    conference in Baltimore MD, USA on September 18-21, 2024.
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="text-slate-500 dark:text-slate-400 font-mono text-xs">[05/2024]</span>
                  <span>MetaMate is now available on EdArXiv.</span>
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
                  <span className="text-slate-400 dark:text-slate-500 mt-0.5">☐</span>
                  <span>
                    <strong>Enhanced Table/Figure Understanding:</strong> add VLM/OCR/TableFormer integration.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-slate-400 dark:text-slate-500 mt-0.5">☐</span>
                  <span>
                    <strong>Enhanced Confidence:</strong> add self-consistency sampling for monte-carlo estimation.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-slate-400 dark:text-slate-500 mt-0.5">☐</span>
                  <span>
                    <strong>Multi-Agent:</strong> incorporate multi-LLM-agent as multi-reviewers.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-slate-400 dark:text-slate-500 mt-0.5">☐</span>
                  <span>
                    <strong>Description Optimization:</strong> automate description filling for coding scheme.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-slate-400 dark:text-slate-500 mt-0.5">☐</span>
                  <span>
                    <strong>Reinforcement Learning:</strong> fine-tuning LLM agent for extraction.
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
                    className="data-[state=active]:bg-jhu-light-blue data-[state=active]:text-white dark:data-[state=active]:bg-jhu-blue dark:data-[state=active]:text-white"
                  >
                    APA
                  </TabsTrigger>
                  <TabsTrigger
                    value="mla"
                    className="data-[state=active]:bg-jhu-light-blue data-[state=active]:text-white dark:data-[state=active]:bg-jhu-blue dark:data-[state=active]:text-white"
                  >
                    MLA
                  </TabsTrigger>
                  <TabsTrigger
                    value="bibtex"
                    className="data-[state=active]:bg-jhu-light-blue data-[state=active]:text-white dark:data-[state=active]:bg-jhu-blue dark:data-[state=active]:text-white"
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
                <Coffee className="h-5 w-5 text-amber-600" />
                Support MetaMate
              </h3>
              <div className="text-sm text-slate-700 dark:text-slate-300 mb-3">
                <p className="mb-2">
                  MetaMate is developed and maintained by Ph.D. students. If you find this tool helpful for your
                  research, consider supporting our work to help keep it free and accessible for everyone.
                </p>
              </div>
              <Button
                variant="outline"
                onClick={() => window.open("/support", "_blank")}
                className="text-sm text-amber-700 border-amber-600/70 hover:bg-amber-100 dark:text-amber-500 dark:border-amber-500/70 dark:hover:bg-amber-900/20"
              >
                <Coffee className="mr-1.5 h-4 w-4" /> Buy Us a Coffee
              </Button>
            </section>
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
