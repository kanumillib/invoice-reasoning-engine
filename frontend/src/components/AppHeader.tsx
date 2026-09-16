import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowRight, Database, History, RotateCcw } from "lucide-react";
import { NavLink } from "react-router-dom";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiDelete, apiGet } from "@/lib/api";
import type { ResetResponse } from "@/lib/invoice-types";

export default function AppHeader({ active }: { active: "run" | "dashboard" }) {
  const queryClient = useQueryClient();
  const connection = useQuery({
    queryKey: ["connection"],
    queryFn: () => apiGet<{ message: string }>("/"),
    retry: false,
    staleTime: 30_000,
  });
  const reset = useMutation({
    mutationFn: () => apiDelete<ResetResponse>("/invoices/session"),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["invoice-history"] });
      void queryClient.invalidateQueries({ queryKey: ["invoice-summary"] });
      toast.success(`${data.deleted} session record${data.deleted === 1 ? "" : "s"} cleared`);
    },
    onError: () => toast.error("Could not clear this session"),
  });

  return (
    <header data-testid="app-header" className="sticky top-0 z-30 border-b border-border/80 bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <NavLink to="/" className="group flex min-w-0 items-center gap-3" data-testid="brand-home-link">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm" data-testid="brand-mark">
            <Activity className="size-4" aria-hidden="true" />
          </span>
          <span className="min-w-0" data-testid="brand-copy">
            <span className="block truncate text-sm font-semibold tracking-tight">Invoice-to-Decision</span>
            <span className="hidden font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground sm:block">Agent workspace</span>
          </span>
        </NavLink>
        <nav className="flex items-center gap-1 rounded-lg border border-border bg-card p-1" aria-label="Primary navigation" data-testid="primary-navigation">
          <NavLink to="/" data-testid="live-run-navigation-link" className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${active === "run" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>
            <ArrowRight className="size-3.5" aria-hidden="true" /> Run invoice
          </NavLink>
          <NavLink to="/dashboard" data-testid="dashboard-navigation-link" className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${active === "dashboard" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>
            <History className="size-3.5" aria-hidden="true" /> Dashboard
          </NavLink>
        </nav>
        <div className="hidden items-center gap-3 md:flex">
          <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground" data-testid="backend-connection-status">
            <span className={`size-1.5 rounded-full ${connection.isSuccess ? "bg-emerald-500" : "bg-amber-500"}`} aria-hidden="true" />
            {connection.isSuccess ? "engine online" : "engine pending"}
          </span>
          <Button type="button" variant="ghost" size="sm" onClick={() => reset.mutate()} disabled={reset.isPending} data-testid="reset-session-button">
            <RotateCcw className="size-3.5" aria-hidden="true" /> Reset session
          </Button>
        </div>
        <Database className="size-4 text-muted-foreground md:hidden" aria-label="Database-backed workspace" data-testid="mobile-database-indicator" />
      </div>
    </header>
  );
}