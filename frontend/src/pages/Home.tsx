import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Check, CheckCircle2, ChevronRight, CircleAlert, CircleX, Clock3, Database, FileText, LoaderCircle, ScanLine, ShieldCheck, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import AppHeader from "@/components/AppHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, apiPostForm } from "@/lib/api";
import type { Decision, InvoiceProcessResponse, PurchaseOrder, SampleInvoice } from "@/lib/invoice-types";

const decisionStyles: Record<Decision, string> = {
  approve: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300",
  flag: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300",
  reject: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300",
  pending: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:bg-sky-500/20 dark:text-sky-300",
};

const sampleColor: Record<string, string> = {
  happy: "border-emerald-500/30 hover:border-emerald-500/60",
  "split-1": "border-sky-500/30 hover:border-sky-500/60",
  "split-2": "border-sky-500/30 hover:border-sky-500/60",
  "over-tolerance": "border-amber-500/30 hover:border-amber-500/60",
  scanned: "border-amber-500/30 hover:border-amber-500/60",
  "missing-total": "border-rose-500/30 hover:border-rose-500/60",
  duplicate: "border-rose-500/30 hover:border-rose-500/60",
};

type LiveStage = "idle" | "extracting" | "matching" | "decision" | "complete";

const currency = (value: number | null | undefined) => value == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
const delay = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

function StageTracker({ stage }: { stage: LiveStage }) {
  const stages = [
    { key: "extracting", label: "Extraction", detail: "Reading invoice fields" },
    { key: "matching", label: "PO matching", detail: "Checking reference + vendor" },
    { key: "decision", label: "Decision rules", detail: "Applying ordered validation" },
  ];
  const activeIndex = stage === "idle" ? -1 : stage === "extracting" ? 0 : stage === "matching" ? 1 : 2;
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center" data-testid="live-pipeline-tracker">
      {stages.map((item, index) => {
        const complete = stage === "complete" || index < activeIndex;
        const active = index === activeIndex && stage !== "complete";
        return (
          <div key={item.key} className="flex min-w-0 flex-1 items-center gap-2" data-testid={`pipeline-stage-${item.key}`}>
            <div className={`flex size-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold transition-all ${complete ? "border-emerald-500 bg-emerald-500 text-white" : active ? "border-primary bg-primary text-primary-foreground shadow-[0_0_0_5px_var(--muted)]" : "border-border bg-muted text-muted-foreground"}`}>
              {complete ? <Check className="size-4" aria-hidden="true" /> : active ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : index + 1}
            </div>
            <div className="min-w-0">
              <p className={`truncate text-xs font-semibold ${active ? "text-foreground" : "text-muted-foreground"}`} data-testid={`pipeline-stage-${item.key}-label`}>{item.label}</p>
              <p className="truncate text-[11px] text-muted-foreground" data-testid={`pipeline-stage-${item.key}-detail`}>{active ? "Processing now" : complete ? "Complete" : item.detail}</p>
            </div>
            {index < stages.length - 1 && <ChevronRight className="ml-auto hidden size-4 text-muted-foreground/50 sm:block" aria-hidden="true" />}
          </div>
        );
      })}
    </div>
  );
}

function ExtractionCard({ result }: { result: InvoiceProcessResponse }) {
  const fields = [
    ["Vendor name", result.extracted.vendor_name],
    ["Invoice number", result.extracted.invoice_number],
    ["Invoice date", result.extracted.invoice_date],
    ["PO reference", result.extracted.po_reference],
    ["Total amount", currency(result.extracted.total_amount)],
  ];
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: "easeOut" }}>
      <Card data-testid="extraction-results-card" className="border-border/80 bg-card/90">
        <CardHeader className="border-b border-border/70 pb-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="label-mono" data-testid="extraction-kicker">STAGE 01 · EXTRACTION</p>
              <CardTitle className="mt-1" data-testid="extraction-title">Invoice fields recovered</CardTitle>
            </div>
            <Badge className={result.extraction_source === "ocr" ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300" : "border-border bg-muted text-foreground"} data-testid="extraction-method-badge">
              {result.extraction_source === "ocr" ? <ScanLine className="size-3" aria-hidden="true" /> : <FileText className="size-3" aria-hidden="true" />}
              {result.extraction_source === "ocr" ? "OCR · Tesseract" : "Text layer"}
            </Badge>
          </div>
          <CardDescription data-testid="extraction-description">The agent records the source path so reviewers can see how reliable the field recovery was.</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-x-6 gap-y-4 pt-5 sm:grid-cols-2">
          {fields.map(([label, value]) => (
            <div key={label} className="border-l-2 border-muted pl-3" data-testid={`extracted-field-${String(label).toLowerCase().replaceAll(" ", "-")}`}>
              <p className="label-mono" data-testid={`extracted-label-${String(label).toLowerCase().replaceAll(" ", "-")}`}>{label}</p>
              <p className={`mt-1 text-sm font-medium ${value === "—" ? "text-rose-600 dark:text-rose-400" : "text-foreground"}`} data-testid={`extracted-value-${String(label).toLowerCase().replaceAll(" ", "-")}`}>{value}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </motion.div>
  );
}

function MatchingCard({ result }: { result: InvoiceProcessResponse }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: "easeOut" }}>
      <Card data-testid="po-matching-card" className="border-border/80 bg-card/90">
        <CardHeader className="border-b border-border/70 pb-4">
          <p className="label-mono" data-testid="matching-kicker">STAGE 02 · MATCHING</p>
          <CardTitle className="mt-1" data-testid="matching-title">{result.matched_po ? "Purchase order matched" : "No purchase order match"}</CardTitle>
          <CardDescription data-testid="matching-description">{result.match_method === "vendor_amount" ? "Fallback match · vendor name + amount within 5%" : result.match_method === "po_reference" ? "Direct lookup · extracted PO reference" : "Both direct and fallback matching paths were exhausted."}</CardDescription>
        </CardHeader>
        <CardContent className="pt-5">
          {result.matched_po ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[["PO number", result.matched_po.po_number], ["Vendor", result.matched_po.vendor_name], ["PO amount", currency(result.matched_po.po_amount)], ["Tolerance", `±${result.matched_po.tolerance_pct}%`]].map(([label, value]) => (
                <div key={label} data-testid={`matched-po-${String(label).toLowerCase().replaceAll(" ", "-")}`}>
                  <p className="label-mono">{label}</p>
                  <p className="mt-1 text-sm font-medium">{value}</p>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-muted-foreground" data-testid="no-po-match-message">No matching PO was found. This invoice cannot proceed to amount validation.</p>}
        </CardContent>
      </Card>
    </motion.div>
  );
}

function DecisionCard({ result }: { result: InvoiceProcessResponse }) {
  const icon = result.decision === "approve" ? <CheckCircle2 className="size-6" /> : result.decision === "flag" ? <CircleAlert className="size-6" /> : result.decision === "reject" ? <CircleX className="size-6" /> : <Clock3 className="size-6" />;
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: "easeOut" }}>
      <Card data-testid="decision-result-card" className={`overflow-hidden border ${decisionStyles[result.decision]} shadow-sm`}>
        <CardHeader className="border-b border-current/10 pb-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="label-mono" data-testid="decision-kicker">STAGE 03 · DECISION</p>
              <CardTitle className="mt-1" data-testid="decision-title">Validation outcome</CardTitle>
            </div>
            <Badge className={`h-7 px-3 text-xs uppercase tracking-wider ${decisionStyles[result.decision]}`} data-testid="decision-badge">{icon}<span data-testid="decision-label">{result.decision}</span></Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 pt-5">
          <div className="flex gap-3" data-testid="decision-reason-block">
            <ShieldCheck className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
            <div><p className="label-mono" data-testid="decision-reason-code">Rule · {result.reason_code.replaceAll("_", " ")}</p><p className="mt-1 text-sm leading-relaxed" data-testid="decision-reason">{result.reason}</p></div>
          </div>
          {result.matched_po && result.progress_pct != null && (
            <div data-testid="cumulative-progress-block">
              <div className="mb-2 flex justify-between gap-3 text-xs"><span data-testid="cumulative-progress-label">Cumulative PO progress</span><span className="font-mono font-semibold" data-testid="cumulative-progress-value">{result.progress_pct}%</span></div>
              <div className="h-2 overflow-hidden rounded-full bg-current/10" aria-label={`Cumulative PO progress ${result.progress_pct}%`}><div className="h-full rounded-full bg-current transition-all duration-700" style={{ width: `${Math.min(result.progress_pct, 100)}%` }} /></div>
              <p className="mt-2 text-xs opacity-75" data-testid="cumulative-progress-amount">{currency(result.cumulative_amount)} billed against {currency(result.matched_po.po_amount)}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}

export default function Home() {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [stage, setStage] = useState<LiveStage>("idle");
  const [result, setResult] = useState<InvoiceProcessResponse | null>(null);
  const [dragging, setDragging] = useState(false);
  const samplesQuery = useQuery({ queryKey: ["invoice-samples"], queryFn: () => apiGet<SampleInvoice[]>("/invoices/samples"), retry: false });
  const posQuery = useQuery({ queryKey: ["purchase-orders"], queryFn: () => apiGet<PurchaseOrder[]>("/invoices/pos"), retry: false });
  const processMutation = useMutation({
    mutationFn: (form: FormData) => apiPostForm<InvoiceProcessResponse>("/invoices/process", form),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invoice-history"] });
      void queryClient.invalidateQueries({ queryKey: ["invoice-summary"] });
    },
  });

  const run = async (form: FormData, label: string) => {
    setResult(null); setStage("extracting");
    try {
      const response = await processMutation.mutateAsync(form);
      await delay(650); setStage("matching");
      await delay(650); setStage("decision");
      await delay(650); setResult(response); setStage("complete");
      toast.success(`${label} processed`);
    } catch {
      setStage("idle");
      toast.error("The invoice could not be processed");
    }
  };

  const runSample = (sample: SampleInvoice) => {
    const form = new FormData(); form.append("sample_key", sample.key); void run(form, sample.label);
  };
  const runUpload = (file: File | null) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) { toast.error("Please choose a PDF invoice"); return; }
    setSelectedFile(file);
  };
  const submitUpload = () => {
    if (!selectedFile) return;
    const form = new FormData(); form.append("file", selectedFile); void run(form, selectedFile.name);
  };

  const samples = samplesQuery.data ?? [];
  return (
    <div className="min-h-svh bg-background text-foreground" data-testid="live-run-page">
      <AppHeader active="run" />
      <main className="mx-auto max-w-7xl space-y-8 px-4 py-7 sm:px-6 lg:px-8">
        <section className="flex flex-col justify-between gap-5 border-b border-border pb-7 lg:flex-row lg:items-end" data-testid="live-run-introduction">
          <div className="max-w-2xl"><p className="label-mono" data-testid="workspace-kicker">OPERATIONS / INVOICE CONTROL</p><h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl" data-testid="live-run-title">Turn an invoice into a decision.</h1><p className="mt-3 text-sm leading-relaxed text-muted-foreground" data-testid="live-run-description">Upload a vendor PDF or run a fixture. The agent extracts the evidence, finds the right PO, then makes its rule-by-rule judgment visible.</p></div>
          <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs text-muted-foreground" data-testid="pipeline-latency-note"><span className="size-2 rounded-full bg-emerald-500" aria-hidden="true" /> Live processing view · staged evidence
          </div>
        </section>

        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-5">
            <Card data-testid="sample-invoice-selector" className="border-border/80 bg-card/90">
              <CardHeader className="border-b border-border/70 pb-4"><div className="flex items-start justify-between gap-3"><div><p className="label-mono" data-testid="sample-kicker">FIXTURE LIBRARY</p><CardTitle className="mt-1" data-testid="sample-title">Run a known scenario</CardTitle></div><Badge variant="outline" data-testid="sample-count-badge">{samples.length || 7} presets</Badge></div><CardDescription data-testid="sample-description">Each fixture is designed to exercise one branch of the validation cascade.</CardDescription></CardHeader>
              <CardContent className="grid gap-2 pt-5">
                {samples.map((sample) => <button type="button" key={sample.key} onClick={() => runSample(sample)} disabled={processMutation.isPending || stage !== "idle" && stage !== "complete"} className={`group rounded-lg border bg-background p-3 text-left transition-all hover:-translate-y-0.5 hover:bg-muted/40 disabled:cursor-wait disabled:opacity-60 ${sampleColor[sample.key] ?? "border-border hover:border-foreground/30"}`} data-testid={`sample-invoice-${sample.key}-button`}><div className="flex items-center justify-between gap-2"><span className="text-sm font-medium" data-testid={`sample-invoice-${sample.key}-label`}>{sample.label}</span><ChevronRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden="true" /></div><span className="mt-1 block text-xs text-muted-foreground" data-testid={`sample-invoice-${sample.key}-description`}>{sample.description}</span></button>)}
              </CardContent>
            </Card>

            <Card data-testid="pdf-upload-card" className="border-border/80 bg-card/90">
              <CardHeader className="pb-4"><p className="label-mono" data-testid="upload-kicker">OR BRING YOUR OWN</p><CardTitle data-testid="upload-title">Upload invoice PDF</CardTitle><CardDescription data-testid="upload-description">Text-layer PDFs are parsed directly. Image-only PDFs surface the local OCR fallback path.</CardDescription></CardHeader>
              <CardContent className="space-y-3">
                <label htmlFor="invoice-pdf" onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); runUpload(event.dataTransfer.files[0] ?? null); }} className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed p-6 text-center transition-all ${dragging ? "border-primary bg-muted" : "border-border bg-muted/30 hover:border-foreground/40 hover:bg-muted/60"}`} data-testid="pdf-dropzone"><UploadCloud className="size-6 text-muted-foreground" aria-hidden="true" /><span className="mt-2 text-sm font-medium" data-testid="upload-dropzone-title">Drop a PDF here or browse</span><span className="mt-1 text-xs text-muted-foreground" data-testid="upload-dropzone-hint">Maximum demo file size 10 MB</span><input ref={fileInput} id="invoice-pdf" type="file" accept="application/pdf,.pdf" className="sr-only" onChange={(event) => runUpload(event.target.files?.[0] ?? null)} data-testid="invoice-pdf-file-input" /></label>
                {selectedFile && <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2" data-testid="selected-pdf-file"><div className="flex min-w-0 items-center gap-2"><FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" /><span className="truncate text-sm" data-testid="selected-pdf-file-name">{selectedFile.name}</span></div><Button type="button" size="sm" onClick={submitUpload} disabled={processMutation.isPending || stage !== "idle" && stage !== "complete"} data-testid="process-upload-button">Process PDF</Button></div>}
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6 lg:col-span-7">
            <Card data-testid="pipeline-card" className="border-border/80 bg-card/90"><CardContent className="p-5 sm:p-6"><div className="mb-5 flex items-center justify-between gap-3"><div><p className="label-mono" data-testid="pipeline-kicker">LIVE RUN</p><h2 className="mt-1 text-lg font-medium" data-testid="pipeline-heading">Evidence pipeline</h2></div>{stage === "idle" ? <Badge variant="outline" data-testid="pipeline-idle-badge">Ready</Badge> : stage === "complete" ? <Badge className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300" data-testid="pipeline-complete-badge"><CheckCircle2 className="size-3" /> Complete</Badge> : <Badge variant="secondary" data-testid="pipeline-processing-badge"><LoaderCircle className="size-3 animate-spin" /> Processing</Badge>}</div><StageTracker stage={stage} /></CardContent></Card>
            {result && (stage === "matching" || stage === "decision" || stage === "complete") && <ExtractionCard result={result} />}
            {result && (stage === "decision" || stage === "complete") && <MatchingCard result={result} />}
            {stage === "decision" && <Card data-testid="decision-processing-card" className="border-primary/30 bg-muted/30"><CardContent className="flex items-center gap-3 p-5"><LoaderCircle className="size-5 animate-spin" /><div><p className="text-sm font-medium" data-testid="decision-processing-title">Cascading validation rules…</p><p className="text-xs text-muted-foreground" data-testid="decision-processing-description">Checking missing data, duplicates, PO match, then cumulative tolerance.</p></div></CardContent></Card>}
            {result && stage === "complete" && <DecisionCard result={result} />}
            {!result && stage === "idle" && <div className="flex min-h-80 flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/20 p-8 text-center" data-testid="pipeline-empty-state"><Database className="size-8 text-muted-foreground/50" aria-hidden="true" /><h2 className="mt-4 text-lg font-medium" data-testid="pipeline-empty-title">Choose an invoice to begin</h2><p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground" data-testid="pipeline-empty-description">The live evidence cards will appear here in order, with the final judgment and its reasoning kept in view.</p></div>}
          </div>
        </div>

        <section className="border-t border-border pt-6" data-testid="po-database-section"><div className="mb-4 flex items-end justify-between gap-3"><div><p className="label-mono" data-testid="po-kicker">REFERENCE DATA</p><h2 className="mt-1 text-xl font-medium" data-testid="po-title">Purchase order database</h2></div><span className="text-xs text-muted-foreground" data-testid="po-count">{posQuery.data?.length ?? 6} seeded records</span></div><Card data-testid="po-database-table" className="border-border/80 bg-card/90"><Table><TableHeader><TableRow><TableHead data-testid="po-table-header-number">PO number</TableHead><TableHead data-testid="po-table-header-vendor">Vendor</TableHead><TableHead data-testid="po-table-header-amount">Amount</TableHead><TableHead data-testid="po-table-header-tolerance">Tolerance</TableHead><TableHead data-testid="po-table-header-status">Status</TableHead></TableRow></TableHeader><TableBody>{(posQuery.data ?? []).map((po) => <TableRow key={po.id} data-testid={`po-row-${po.po_number}`}><TableCell className="font-mono text-xs">{po.po_number}</TableCell><TableCell>{po.vendor_name}</TableCell><TableCell>{currency(po.po_amount)}</TableCell><TableCell>±{po.tolerance_pct}%</TableCell><TableCell><Badge variant={po.status === "open" ? "secondary" : "outline"}>{po.status}</Badge></TableCell></TableRow>)}</TableBody></Table></Card></section>
      </main>
    </div>
  );
}