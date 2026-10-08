import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import type { LucideIcon } from "lucide-react"
import {
  AlertCircle,
  CalendarDays,
  CircleDollarSign,
  Clock3,
  Eye,
  History,
  Lightbulb,
  ListChecks,
  LoaderCircle,
  PackageSearch,
  ReceiptText,
  RefreshCw,
  ShieldAlert,
  ShoppingBasket,
  Sparkles,
  TrendingUp,
  X,
} from "lucide-react"
import { useState } from "react"

import { type AIDailyBriefingPublic, AiService } from "@/client"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

const pageSize = 6

const currencyFormatter = new Intl.NumberFormat("en-AU", {
  style: "currency",
  currency: "AUD",
})

const quantityFormatter = new Intl.NumberFormat("en-AU", {
  maximumFractionDigits: 3,
})

function formatReportDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number)
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "full" }).format(
    new Date(year, month - 1, day),
  )
}

function formatGeneratedAt(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    timeZone: "Australia/Sydney",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function formatCurrency(value: string): string {
  return currencyFormatter.format(Number(value))
}

function formatQuantity(value: string): string {
  return quantityFormatter.format(Number(value))
}

function getErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)
      ?.detail
    if (typeof detail === "string") return detail
  }
  return "Briefing history could not be loaded. Check the backend and try again."
}

function SourceMetric({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon
  label: string
  value: string
}) {
  return (
    <div className="rounded-lg border bg-background/70 p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="size-4" />
        {label}
      </div>
      <p className="mt-2 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  )
}

function SuggestionSection({
  icon: Icon,
  iconClassName,
  items,
  title,
}: {
  icon: LucideIcon
  iconClassName: string
  items: string[]
  title: string
}) {
  return (
    <div className="rounded-xl border bg-background/70 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Icon className={cn("size-4", iconClassName)} />
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      {items.length > 0 ? (
        <ul className="space-y-2 text-sm text-muted-foreground">
          {items.map((item) => (
            <li key={item} className="flex items-start gap-2">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-current" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">None recorded.</p>
      )}
    </div>
  )
}

function BriefingDetails({
  briefing,
  onOpenChange,
}: {
  briefing: AIDailyBriefingPublic | null
  onOpenChange: (open: boolean) => void
}) {
  if (!briefing) return null

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <div className="mb-1 flex flex-wrap gap-2 pr-8">
            <Badge variant="secondary">
              {formatReportDate(briefing.report_date)}
            </Badge>
            {briefing.generation_mode === "automation" ? (
              <Badge>Automated</Badge>
            ) : null}
            <Badge variant="outline">{briefing.model}</Badge>
          </div>
          <DialogTitle className="text-xl leading-7">
            {briefing.headline}
          </DialogTitle>
          <DialogDescription>
            Generated {formatGeneratedAt(briefing.generated_at)} from the saved
            operations snapshot.
          </DialogDescription>
        </DialogHeader>

        <p className="text-sm leading-6 text-muted-foreground">
          {briefing.summary}
        </p>

        <div className="grid gap-3 lg:grid-cols-3">
          <SuggestionSection
            title="Priorities"
            items={briefing.priorities}
            icon={ListChecks}
            iconClassName="text-sky-600 dark:text-sky-400"
          />
          <SuggestionSection
            title="Risks"
            items={briefing.risks}
            icon={ShieldAlert}
            iconClassName="text-rose-600 dark:text-rose-400"
          />
          <SuggestionSection
            title="Opportunities"
            items={briefing.opportunities}
            icon={Lightbulb}
            iconClassName="text-amber-600 dark:text-amber-400"
          />
        </div>

        <section className="space-y-3 border-t pt-5">
          <div>
            <h3 className="font-semibold">Grounded source snapshot</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              The operating metrics supplied to the local model ·{" "}
              {briefing.source.timezone}
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <SourceMetric
              icon={CircleDollarSign}
              label="Revenue"
              value={formatCurrency(briefing.source.revenue)}
            />
            <SourceMetric
              icon={ReceiptText}
              label="Sales"
              value={briefing.source.sales_count.toLocaleString("en-AU")}
            />
            <SourceMetric
              icon={ShoppingBasket}
              label="Units sold"
              value={formatQuantity(briefing.source.units_sold)}
            />
            <SourceMetric
              icon={TrendingUp}
              label="Average sale"
              value={formatCurrency(briefing.source.average_sale_value)}
            />
            <SourceMetric
              icon={PackageSearch}
              label="Low stock"
              value={briefing.source.low_stock_count.toLocaleString("en-AU")}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border p-4">
              <h4 className="text-sm font-semibold">Top products</h4>
              {briefing.source.top_products.length > 0 ? (
                <div className="mt-3 divide-y">
                  {briefing.source.top_products.map((product) => (
                    <div
                      className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0"
                      key={product.product_id}
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {product.product_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatQuantity(product.quantity_sold)} units
                        </p>
                      </div>
                      <p className="text-sm font-semibold tabular-nums">
                        {formatCurrency(product.revenue)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">
                  No sales recorded for this day.
                </p>
              )}
            </div>

            <div className="rounded-xl border p-4">
              <h4 className="text-sm font-semibold">Low-stock products</h4>
              {briefing.source.low_stock.length > 0 ? (
                <div className="mt-3 divide-y">
                  {briefing.source.low_stock.map((product) => (
                    <div
                      className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0"
                      key={product.product_id}
                    >
                      <p className="truncate text-sm font-medium">
                        {product.product_name}
                      </p>
                      <p className="text-xs text-muted-foreground tabular-nums">
                        {formatQuantity(product.quantity_on_hand)} / reorder at{" "}
                        {formatQuantity(product.reorder_level)} {product.unit}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">
                  No low-stock products in this snapshot.
                </p>
              )}
            </div>
          </div>
        </section>
      </DialogContent>
    </Dialog>
  )
}

export const Route = createFileRoute("/_layout/briefings")({
  component: BriefingHistory,
  head: () => ({
    meta: [{ title: "Briefing History | OpsPilot" }],
  }),
})

function BriefingHistory() {
  const [reportDate, setReportDate] = useState("")
  const [page, setPage] = useState(0)
  const [selectedBriefing, setSelectedBriefing] =
    useState<AIDailyBriefingPublic | null>(null)

  const historyQuery = useQuery({
    queryKey: ["ai-daily-briefings", reportDate, page],
    queryFn: async () => {
      const response = await AiService.readDailyBriefingHistory({
        query: {
          report_date: reportDate || undefined,
          skip: page * pageSize,
          limit: pageSize,
        },
      })
      return response.data
    },
  })

  const briefings = historyQuery.data?.data ?? []
  const count = historyQuery.data?.count ?? 0
  const totalPages = Math.max(1, Math.ceil(count / pageSize))
  const firstResult = count === 0 ? 0 : page * pageSize + 1
  const lastResult = Math.min((page + 1) * pageSize, count)

  return (
    <div className="space-y-6" data-testid="briefing-history">
      <section className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-violet-500/15 via-background to-background p-6 shadow-sm md:p-8">
        <div className="absolute -right-20 -top-24 size-72 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="relative flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
          <div className="max-w-2xl">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-violet-600 dark:text-violet-400">
              <History className="size-4" />
              OpsPilot audit trail
            </div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
              AI briefing history
            </h1>
            <p className="mt-3 text-muted-foreground">
              Review every saved briefing alongside the exact operating data
              that grounded it.
            </p>
          </div>
          <Badge className="w-fit" variant="secondary">
            {count.toLocaleString("en-AU")} saved
          </Badge>
        </div>
      </section>

      <Card>
        <CardHeader className="border-b">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <CardTitle>Saved briefings</CardTitle>
              <CardDescription className="mt-1">
                Filter by business date or inspect the complete history.
              </CardDescription>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <div className="relative">
                <CalendarDays className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  aria-label="Filter briefings by report date"
                  className="w-full pl-9 sm:w-44"
                  type="date"
                  value={reportDate}
                  onChange={(event) => {
                    setReportDate(event.target.value)
                    setPage(0)
                  }}
                />
              </div>
              {reportDate ? (
                <Button
                  aria-label="Clear report date filter"
                  size="icon"
                  variant="outline"
                  onClick={() => {
                    setReportDate("")
                    setPage(0)
                  }}
                >
                  <X />
                </Button>
              ) : null}
              <Button
                variant="outline"
                onClick={() => void historyQuery.refetch()}
                disabled={historyQuery.isFetching}
              >
                {historyQuery.isFetching ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <RefreshCw />
                )}
                Refresh
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="py-6">
          {historyQuery.error ? (
            <Alert variant="destructive">
              <AlertCircle />
              <AlertTitle>History unavailable</AlertTitle>
              <AlertDescription>
                {getErrorMessage(historyQuery.error)}
              </AlertDescription>
            </Alert>
          ) : historyQuery.isPending ? (
            <div className="grid gap-4 lg:grid-cols-2" role="status">
              {Array.from({ length: 4 }, (_, index) => (
                <Skeleton className="h-72 rounded-xl" key={index} />
              ))}
            </div>
          ) : briefings.length === 0 ? (
            <div className="flex min-h-72 flex-col items-center justify-center text-center">
              <div className="mb-4 rounded-full bg-violet-500/10 p-4">
                <Sparkles className="size-7 text-violet-600 dark:text-violet-400" />
              </div>
              <p className="font-medium">
                {reportDate
                  ? "No briefing saved for this date"
                  : "No saved briefings yet"}
              </p>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Generate a daily briefing from the dashboard and it will appear
                here automatically.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {briefings.map((briefing) => (
                <article
                  className="flex flex-col rounded-xl border bg-background/70 p-5"
                  key={briefing.id}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">
                      {formatReportDate(briefing.report_date)}
                    </Badge>
                    {briefing.generation_mode === "automation" ? (
                      <Badge>Automated</Badge>
                    ) : null}
                    <Badge variant="outline">{briefing.model}</Badge>
                  </div>
                  <h2 className="mt-4 text-lg font-semibold leading-7">
                    {briefing.headline}
                  </h2>
                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-muted-foreground">
                    {briefing.summary}
                  </p>

                  <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <SourceMetric
                      icon={CircleDollarSign}
                      label="Revenue"
                      value={formatCurrency(briefing.source.revenue)}
                    />
                    <SourceMetric
                      icon={ReceiptText}
                      label="Sales"
                      value={briefing.source.sales_count.toLocaleString(
                        "en-AU",
                      )}
                    />
                    <SourceMetric
                      icon={ShoppingBasket}
                      label="Units"
                      value={formatQuantity(briefing.source.units_sold)}
                    />
                    <SourceMetric
                      icon={PackageSearch}
                      label="Low stock"
                      value={briefing.source.low_stock_count.toLocaleString(
                        "en-AU",
                      )}
                    />
                  </div>

                  <div className="mt-5 flex flex-col justify-between gap-3 border-t pt-4 sm:flex-row sm:items-center">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock3 className="size-4" />
                      {formatGeneratedAt(briefing.generated_at)}
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setSelectedBriefing(briefing)}
                    >
                      <Eye />
                      Review briefing
                    </Button>
                  </div>
                </article>
              ))}
            </div>
          )}

          {!historyQuery.isPending && !historyQuery.error && count > 0 ? (
            <div className="mt-6 flex flex-col items-center justify-between gap-3 border-t pt-5 sm:flex-row">
              <p className="text-sm text-muted-foreground">
                Showing {firstResult}–{lastResult} of {count}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0 || historyQuery.isFetching}
                  onClick={() => setPage((current) => current - 1)}
                >
                  Previous
                </Button>
                <span className="min-w-20 text-center text-sm text-muted-foreground">
                  Page {page + 1} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page + 1 >= totalPages || historyQuery.isFetching}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <BriefingDetails
        briefing={selectedBriefing}
        onOpenChange={(open) => {
          if (!open) setSelectedBriefing(null)
        }}
      />
    </div>
  )
}
