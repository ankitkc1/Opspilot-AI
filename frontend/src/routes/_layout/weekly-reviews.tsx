import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import type { LucideIcon } from "lucide-react"
import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  CalendarDays,
  CalendarRange,
  CircleDollarSign,
  Clock3,
  Eye,
  ListChecks,
  LoaderCircle,
  Minus,
  ReceiptText,
  RefreshCw,
  ShieldAlert,
  ShoppingBasket,
  Sparkles,
  TrendingUp,
  Trophy,
  X,
} from "lucide-react"
import { useState } from "react"

import { type AIWeeklyReviewPublic, AiService } from "@/client"
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

const pageSize = 6

const currencyFormatter = new Intl.NumberFormat("en-AU", {
  style: "currency",
  currency: "AUD",
})

const quantityFormatter = new Intl.NumberFormat("en-AU", {
  maximumFractionDigits: 3,
})

function formatDate(value: string, style: "short" | "medium" = "medium") {
  const [year, month, day] = value.split("-").map(Number)
  return new Intl.DateTimeFormat("en-AU", { dateStyle: style }).format(
    new Date(year, month - 1, day),
  )
}

function formatPeriod(review: AIWeeklyReviewPublic): string {
  return `${formatDate(review.period_start_date)} – ${formatDate(review.period_end_date)}`
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
  return "Weekly review history could not be loaded. Check the backend and try again."
}

function ChangeIndicator({ value }: { value: string | null }) {
  if (value === null) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-sky-700 dark:text-sky-300">
        <ArrowUpRight className="size-3.5" />
        New vs prior period
      </span>
    )
  }

  const change = Number(value)
  if (change === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Minus className="size-3.5" />
        No change
      </span>
    )
  }

  const isPositive = change > 0
  const Icon = isPositive ? ArrowUpRight : ArrowDownRight
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs font-medium",
        isPositive
          ? "text-emerald-700 dark:text-emerald-300"
          : "text-rose-700 dark:text-rose-300",
      )}
    >
      <Icon className="size-3.5" />
      {Math.abs(change).toLocaleString("en-AU", {
        maximumFractionDigits: 1,
      })}
      % vs prior period
    </span>
  )
}

function SourceMetric({
  change,
  icon: Icon,
  label,
  value,
}: {
  change?: string | null
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
      {change !== undefined ? (
        <div className="mt-1">
          <ChangeIndicator value={change} />
        </div>
      ) : null}
    </div>
  )
}

function ReviewSection({
  emptyMessage,
  icon: Icon,
  iconClassName,
  items,
  title,
}: {
  emptyMessage: string
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
            <li className="flex items-start gap-2" key={item}>
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-current" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyMessage}</p>
      )}
    </div>
  )
}

function WeeklyReviewDetails({
  onOpenChange,
  review,
}: {
  onOpenChange: (open: boolean) => void
  review: AIWeeklyReviewPublic | null
}) {
  if (!review) return null

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <div className="mb-1 flex flex-wrap gap-2 pr-8">
            <Badge variant="secondary">{formatPeriod(review)}</Badge>
            <Badge variant="outline">{review.model}</Badge>
          </div>
          <DialogTitle className="text-xl leading-7">
            {review.headline}
          </DialogTitle>
          <DialogDescription>
            Generated {formatGeneratedAt(review.generated_at)} from the saved
            seven-day trend snapshot.
          </DialogDescription>
        </DialogHeader>

        <p className="text-sm leading-6 text-muted-foreground">
          {review.summary}
        </p>

        <div className="grid gap-3 lg:grid-cols-3">
          <ReviewSection
            emptyMessage="No clear wins were recorded."
            icon={Trophy}
            iconClassName="text-emerald-600 dark:text-emerald-400"
            items={review.wins}
            title="Wins"
          />
          <ReviewSection
            emptyMessage="No specific concerns were recorded."
            icon={ShieldAlert}
            iconClassName="text-rose-600 dark:text-rose-400"
            items={review.concerns}
            title="Concerns"
          />
          <ReviewSection
            emptyMessage="No priorities were recorded."
            icon={ListChecks}
            iconClassName="text-sky-600 dark:text-sky-400"
            items={review.priorities}
            title="Next-week priorities"
          />
        </div>

        <section className="space-y-4 border-t pt-5">
          <div>
            <h3 className="font-semibold">Grounded source snapshot</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              The exact {review.source.days}-day comparison supplied to the
              local model · {review.source.timezone}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <SourceMetric
              change={review.source.previous_period.revenue_change_percent}
              icon={CircleDollarSign}
              label="Revenue"
              value={formatCurrency(review.source.revenue)}
            />
            <SourceMetric
              change={review.source.previous_period.sales_count_change_percent}
              icon={ReceiptText}
              label="Sales"
              value={review.source.sales_count.toLocaleString("en-AU")}
            />
            <SourceMetric
              change={review.source.previous_period.units_sold_change_percent}
              icon={ShoppingBasket}
              label="Units sold"
              value={formatQuantity(review.source.units_sold)}
            />
            <SourceMetric
              icon={TrendingUp}
              label="Average sale"
              value={formatCurrency(review.source.average_sale_value)}
            />
          </div>

          <div className="rounded-xl border">
            <div className="border-b px-4 py-3">
              <h4 className="text-sm font-semibold">Daily source values</h4>
              <p className="mt-1 text-xs text-muted-foreground">
                Compared with{" "}
                {formatDate(review.source.previous_period.start_date)}
                {" – "}
                {formatDate(review.source.previous_period.end_date)}.
              </p>
            </div>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead className="text-right">Revenue</TableHead>
                    <TableHead className="text-right">Sales</TableHead>
                    <TableHead className="text-right">Units</TableHead>
                    <TableHead className="text-right">Average sale</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {review.source.daily.map((day) => (
                    <TableRow key={day.report_date}>
                      <TableCell className="font-medium">
                        {formatDate(day.report_date)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatCurrency(day.revenue)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {day.sales_count.toLocaleString("en-AU")}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatQuantity(day.units_sold)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatCurrency(day.average_sale_value)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        </section>
      </DialogContent>
    </Dialog>
  )
}

export const Route = createFileRoute("/_layout/weekly-reviews")({
  component: WeeklyReviewHistory,
  head: () => ({
    meta: [{ title: "Weekly Review History | OpsPilot" }],
  }),
})

function WeeklyReviewHistory() {
  const [endDate, setEndDate] = useState("")
  const [page, setPage] = useState(0)
  const [selectedReview, setSelectedReview] =
    useState<AIWeeklyReviewPublic | null>(null)

  const historyQuery = useQuery({
    queryKey: ["ai-weekly-reviews", endDate, page],
    queryFn: async () => {
      const response = await AiService.readWeeklyReviewHistory({
        query: {
          end_date: endDate || undefined,
          skip: page * pageSize,
          limit: pageSize,
        },
      })
      return response.data
    },
  })

  const reviews = historyQuery.data?.data ?? []
  const count = historyQuery.data?.count ?? 0
  const totalPages = Math.max(1, Math.ceil(count / pageSize))
  const firstResult = count === 0 ? 0 : page * pageSize + 1
  const lastResult = Math.min((page + 1) * pageSize, count)

  return (
    <div className="space-y-6" data-testid="weekly-review-history">
      <section className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-violet-500/15 via-background to-background p-6 shadow-sm md:p-8">
        <div className="absolute -right-20 -top-24 size-72 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="relative flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
          <div className="max-w-2xl">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-violet-600 dark:text-violet-400">
              <CalendarRange className="size-4" />
              OpsPilot audit trail
            </div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Weekly review history
            </h1>
            <p className="mt-3 text-muted-foreground">
              Reopen every saved weekly review and verify it against the exact
              trend comparison that grounded it.
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
              <CardTitle>Saved weekly reviews</CardTitle>
              <CardDescription className="mt-1">
                Filter by period end date or inspect the complete history.
              </CardDescription>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <div className="relative">
                <CalendarDays className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  aria-label="Filter weekly reviews by period end date"
                  className="w-full pl-9 sm:w-44"
                  onChange={(event) => {
                    setEndDate(event.target.value)
                    setPage(0)
                  }}
                  type="date"
                  value={endDate}
                />
              </div>
              {endDate ? (
                <Button
                  aria-label="Clear period end date filter"
                  onClick={() => {
                    setEndDate("")
                    setPage(0)
                  }}
                  size="icon"
                  variant="outline"
                >
                  <X />
                </Button>
              ) : null}
              <Button
                disabled={historyQuery.isFetching}
                onClick={() => void historyQuery.refetch()}
                variant="outline"
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
          ) : reviews.length === 0 ? (
            <div className="flex min-h-72 flex-col items-center justify-center text-center">
              <div className="mb-4 rounded-full bg-violet-500/10 p-4">
                <Sparkles className="size-7 text-violet-600 dark:text-violet-400" />
              </div>
              <p className="font-medium">
                {endDate
                  ? "No weekly review ends on this date"
                  : "No saved weekly reviews yet"}
              </p>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Generate a review from the seven-day Trends view and it will
                appear here automatically.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {reviews.map((review) => (
                <article
                  className="flex flex-col rounded-xl border bg-background/70 p-5"
                  key={review.id}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{formatPeriod(review)}</Badge>
                    <Badge variant="outline">{review.model}</Badge>
                  </div>
                  <h2 className="mt-4 text-lg font-semibold leading-7">
                    {review.headline}
                  </h2>
                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-muted-foreground">
                    {review.summary}
                  </p>

                  <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <SourceMetric
                      icon={CircleDollarSign}
                      label="Revenue"
                      value={formatCurrency(review.source.revenue)}
                    />
                    <SourceMetric
                      icon={ReceiptText}
                      label="Sales"
                      value={review.source.sales_count.toLocaleString("en-AU")}
                    />
                    <SourceMetric
                      icon={ShoppingBasket}
                      label="Units"
                      value={formatQuantity(review.source.units_sold)}
                    />
                    <SourceMetric
                      icon={ListChecks}
                      label="Priorities"
                      value={review.priorities.length.toLocaleString("en-AU")}
                    />
                  </div>

                  <div className="mt-5 flex flex-col justify-between gap-3 border-t pt-4 sm:flex-row sm:items-center">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock3 className="size-4" />
                      {formatGeneratedAt(review.generated_at)}
                    </div>
                    <Button
                      onClick={() => setSelectedReview(review)}
                      size="sm"
                      variant="outline"
                    >
                      <Eye />
                      Review details
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
                  disabled={page === 0 || historyQuery.isFetching}
                  onClick={() => setPage((current) => current - 1)}
                  size="sm"
                  variant="outline"
                >
                  Previous
                </Button>
                <span className="min-w-20 text-center text-sm text-muted-foreground">
                  Page {page + 1} of {totalPages}
                </span>
                <Button
                  disabled={page + 1 >= totalPages || historyQuery.isFetching}
                  onClick={() => setPage((current) => current + 1)}
                  size="sm"
                  variant="outline"
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <WeeklyReviewDetails
        onOpenChange={(open) => {
          if (!open) setSelectedReview(null)
        }}
        review={selectedReview}
      />
    </div>
  )
}
