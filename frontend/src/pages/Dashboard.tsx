import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, CircleX, Clock3, FileText, Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";

import AppHeader from "@/components/AppHeader";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet } from "@/lib/api";
import type { Decision, InvoiceProcessResponse, Summary } from "@/lib/invoice-types";

const decisionStyles: Record<Decision, string> = {
  approve: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300",
  flag: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300",
  reject: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300",
  pending: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:bg-sky-500/20 dark:text-sky-300",
};
const currency = (value: number | null | undefined) => value == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
const icons: Record<Decision, ReactNode> = { approve: <CheckCircle2 className="size-4" />, flag: <CircleAlert className="size-4" />, reject: <CircleX className="size-4" />, pending: <Clock3 className="size-4" /> };

export default function Dashboard() {
  const [search, setSearch] = useState("");
  const historyQuery = useQuery({ queryKey: ["invoice-history"], queryFn: () => apiGet<InvoiceProcessResponse[]>("/invoices/history"), retry: false });
  const summaryQuery = useQuery({ queryKey: ["invoice-summary"], queryFn: () => apiGet<Summary>("/invoices/summary"), retry: false });
  const summary = summaryQuery.data ?? { total: 0, approve: 0, flag: 0, reject: 0, pending: 0 };
  const history = useMemo(() => (historyQuery.data ?? []).filter((item) => `${item.extracted.invoice_number ?? ""} ${item.extracted.vendor_name ?? ""} ${item.reason}`.toLowerCase().includes(search.toLowerCase())), [historyQuery.data, search]);
  const metrics: Array<{ key: keyof Summary; label: string; detail: string; color: string }> = [
    { key: "total", label: "Processed", detail: "this session", color: "text-foreground" },
    { key: "approve", label: "Approved", detail: "within tolerance", color: "text-emerald-600 dark:text-emerald-400" },
    { key: "flag", label: "Flagged", detail: "needs review", color: "text-amber-600 dark:text-amber-400" },
    { key: "reject", label: "Rejected", detail: "hard stop", color: "text-rose-600 dark:text-rose-400" },
    { key: "pending", label: "Pending", detail: "awaiting remainder", color: "text-sky-600 dark:text-sky-400" },
  ];
  return (
    <div className="min-h-svh bg-background text-foreground" data-testid="dashboard-page">
      <AppHeader active="dashboard" />
      <main className="mx-auto max-w-7xl space-y-8 px-4 py-7 sm:px-6 lg:px-8">
        <section className="flex flex-col justify-between gap-5 border-b border-border pb-7 lg:flex-row lg:items-end" data-testid="dashboard-introduction"><div><p className="label-mono" data-testid="dashboard-kicker">AUDIT VIEW / SESSION HISTORY</p><h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl" data-testid="dashboard-title">Decision dashboard.</h1><p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground" data-testid="dashboard-description">A compact record of what the agent saw, how it matched, and why it reached each outcome.</p></div><div className="flex items-center gap-2 text-xs text-muted-foreground" data-testid="dashboard-refresh-note"><FileText className="size-4" /> Updates after each live run</div></section>
        <section className="grid grid-cols-2 gap-3 md:grid-cols-5" data-testid="summary-metrics">
          {metrics.map((metric) => <Card key={metric.key} data-testid={`summary-card-${metric.key}`} className="border-border/80 bg-card/90"><CardContent className="p-4 sm:p-5"><p className="label-mono" data-testid={`summary-label-${metric.key}`}>{metric.label}</p><p className={`mt-2 text-3xl font-semibold tracking-tight ${metric.color}`} data-testid={`summary-value-${metric.key}`}>{summary[metric.key]}</p><p className="mt-1 text-xs text-muted-foreground" data-testid={`summary-detail-${metric.key}`}>{metric.detail}</p></CardContent></Card>)}
        </section>
        <Card data-testid="history-dashboard-section" className="border-border/80 bg-card/90">
          <CardHeader className="border-b border-border/70 pb-4"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><p className="label-mono" data-testid="history-kicker">PROCESSING LOG</p><CardTitle className="mt-1" data-testid="history-title">Invoice history</CardTitle></div><div className="relative w-full sm:w-72"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" /><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search vendor, invoice, reason" className="pl-9" data-testid="history-search-input" /></div></div></CardHeader>
          <CardContent className="p-0"><Table><TableHeader><TableRow><TableHead data-testid="history-header-invoice">Invoice</TableHead><TableHead data-testid="history-header-vendor">Vendor</TableHead><TableHead data-testid="history-header-amount">Amount</TableHead><TableHead data-testid="history-header-decision">Decision</TableHead><TableHead data-testid="history-header-reason">Reason</TableHead></TableRow></TableHeader><TableBody>{history.map((item) => <TableRow key={item.id} data-testid={`history-row-${item.id}`}><TableCell><p className="font-mono text-xs font-medium">{item.extracted.invoice_number ?? "Missing"}</p><p className="mt-1 text-[11px] text-muted-foreground">{new Date(item.processed_at).toLocaleDateString()}</p></TableCell><TableCell>{item.extracted.vendor_name ?? "Unknown vendor"}</TableCell><TableCell>{currency(item.extracted.total_amount)}</TableCell><TableCell><Badge className={`gap-1 ${decisionStyles[item.decision]}`} data-testid={`history-decision-${item.id}`}>{icons[item.decision]} {item.decision}</Badge></TableCell><TableCell className="max-w-md whitespace-normal text-xs leading-relaxed text-muted-foreground">{item.reason}</TableCell></TableRow>)}</TableBody></Table>{history.length === 0 && <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center" data-testid="history-empty-state"><FileText className="size-7 text-muted-foreground/50" aria-hidden="true" /><p className="text-sm font-medium" data-testid="history-empty-title">{search ? "No matching invoices" : "No invoices processed yet"}</p><p className="max-w-sm text-xs text-muted-foreground" data-testid="history-empty-description">{search ? "Try a different vendor, invoice number, or reason." : "Run a sample from the Live Run view to create your first audit record."}</p></div>}</CardContent>
        </Card>
      </main>
    </div>
  );
}