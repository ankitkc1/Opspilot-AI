import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import type { LucideIcon } from "lucide-react"
import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  CalendarDays,
  CircleCheck,
  CircleDollarSign,
  ListChecks,
  LoaderCircle,
  Minus,
  Plus,
  ReceiptText,
  RefreshCw,
  ShieldAlert,
  ShoppingBasket,
  Sparkles,
  TrendingUp,
  Trophy,
} from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import {
  type ActionItemCreate,
  ActionsService,
  type AIWeeklyReviewPublic,
  AiService,
  DashboardService,
  type DashboardTrendDayPublic,
  type TrendDays,
} from "@/client"
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
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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

const currencyFormatter = new Intl.NumberFormat("en-AU", {
  style: "currency",
  currency: "AUD",
})

const quantityFormatter = new Intl.NumberFormat("en-AU", {
  maximumFractionDigits: 3,
})

function getSydneyDate(): string {
  const parts = new Intl.DateTimeFormat("en-AU", {
    timeZone: "Australia/Sydney",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date())
  const values = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  )
  return `${values.year}-${values.month}-${values.day}`
}

function formatDate(value: string, style: "short" | "medium" = "medium") {
  const [year, month, day] = value.split("-").map(Number)
  return new Intl.DateTimeFormat("en-AU", { dateStyle: style }).format(
    new Date(year, month - 1, day),
  )
}

function formatChartDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number)
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
  }).format(new Date(year, month - 1, day))
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
  return "Operations trends could not be loaded. Check the backend and try again."
}

function isWeeklyReview(value: unknown): value is AIWeeklyReviewPublic {
  return typeof value === "object" && value !== null && "source" in value
}

function formatGeneratedAt(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    timeZone: "Australia/Sydney",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function getWeeklyReviewError(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)
      ?.detail
    if (typeof detail === "string") return detail
  }

  return "The weekly review could not be loaded or created. Check the backend and Ollama, then try again."
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

function TrendMetric({
  change,
  icon: Icon,
  iconClassName,
  label,
  value,
}: {
  change?: string | null
  icon: LucideIcon
  iconClassName: string
  label: string
  value: string
}) {
  return (
    <Card className="gap-4 py-5">
      <CardContent className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="mt-2 truncate text-3xl font-semibold tracking-tight">
            {value}
          </p>
          <div className="mt-2 min-h-5">
            {change !== undefined ? (
              <ChangeIndicator value={change} />
            ) : (
              <span className="text-xs text-muted-foreground">
                Current period
              </span>
            )}
          </div>
        </div>
        <div className={cn("rounded-xl p-3", iconClassName)}>
          <Icon className="size-5" />
        </div>
      </CardContent>
    </Card>
  )
}

function RevenueChart({ daily }: { daily: DashboardTrendDayPublic[] }) {
  const maxRevenue = Math.max(...daily.map((day) => Number(day.revenue)), 1)

  return (
    <div className="overflow-x-auto pb-2">
      <div
        className="flex h-72 items-end gap-2 border-b px-1 pt-10"
        aria-label="Daily revenue chart"
        role="img"
        style={{ minWidth: `${Math.max(680, daily.length * 42)}px` }}
      >
        {daily.map((day) => {
          const revenue = Number(day.revenue)
          const height =
            revenue === 0 ? 1 : Math.max(4, (revenue / maxRevenue) * 100)
          return (
            <div
              className="flex h-full min-w-5 flex-1 flex-col items-center justify-end gap-2"
              key={day.report_date}
              title={`${formatDate(day.report_date)}: ${formatCurrency(day.revenue)}`}
            >
              {revenue > 0 ? (
                <span className="text-[10px] font-medium tabular-nums text-muted-foreground">
                  {currencyFormatter.format(revenue).replace(".00", "")}
                </span>
              ) : null}
              <div
                className={cn(
                  "w-full max-w-10 rounded-t bg-primary/80 transition-all",
                  revenue === 0 && "bg-muted",
                )}
                style={{ height: `${height}%` }}
              />
              <span className="whitespace-nowrap text-[10px] text-muted-foreground">
                {formatChartDate(day.report_date)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function WeeklyReviewList({
  emptyMessage,
  icon: Icon,
  iconClassName,
  items,
  isAdded,
  isCreating,
  onCreateAction,
  title,
}: {
  emptyMessage: string
  icon: LucideIcon
  iconClassName: string
  items: string[]
  isAdded?: (item: string) => boolean
  isCreating?: (item: string) => boolean
  onCreateAction?: (item: string) => void
  title: string
}) {
  return (
    <div className="rounded-xl border bg-background/70 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Icon className={cn("size-4", iconClassName)} />
        <h3 className="font-medium">{title}</h3>
      </div>
      {items.length > 0 ? (
        <ul className="space-y-2 text-sm text-muted-foreground">
          {items.map((item) => (
            <li className="flex items-start gap-2" key={item}>
              <span aria-hidden="true" className="mt-0.5 text-foreground/50">
                •
              </span>
              <span className="min-w-0 flex-1">{item}</span>
              {onCreateAction ? (
                <Button
                  className="shrink-0"
                  disabled={isAdded?.(item) || isCreating?.(item)}
                  onClick={() => onCreateAction(item)}
                  size="sm"
                  variant="outline"
                >
                  {isCreating?.(item) ? (
                    <LoaderCircle className="animate-spin" />
                  ) : isAdded?.(item) ? (
                    <CircleCheck />
                  ) : (
                    <Plus />
                  )}
                  {isAdded?.(item) ? "Added" : "Add"}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyMessage}</p>
      )}
    </div>
  )
}

function WeeklyReview({
  addedPriorities,
  canGenerate,
  creatingAction,
  error,
  isGenerating,
  isLoading,
  isStale,
  onGenerate,
  onCreatePriority,
  review,
}: {
  addedPriorities: Set<string>
  canGenerate: boolean
  creatingAction?: ActionItemCreate
  error: unknown
  isGenerating: boolean
  isLoading: boolean
  isStale: boolean
  onGenerate: () => void
  onCreatePriority: (priority: string) => void
  review?: AIWeeklyReviewPublic
}) {
  return (
    <Card className="overflow-hidden border-violet-500/25 bg-gradient-to-br from-violet-500/10 via-background to-background">
      <CardHeader className="border-b border-violet-500/15">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-violet-500/15 p-2.5 text-violet-600 dark:text-violet-400">
              <Sparkles className="size-5" />
            </div>
            <div>
              <CardTitle>AI weekly operations review</CardTitle>
              <CardDescription>
                Wins, concerns, and next-week priorities grounded in this
                seven-day comparison
              </CardDescription>
            </div>
          </div>
          <Button
            className="shrink-0"
            disabled={!canGenerate || isGenerating || isLoading}
            onClick={onGenerate}
          >
            {isGenerating ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <Sparkles />
            )}
            {isGenerating
              ? "Generating..."
              : isStale
                ? "Update review"
                : review
                  ? "Regenerate"
                  : "Generate review"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {!canGenerate ? (
          <Alert>
            <CalendarDays />
            <AlertTitle>Select the 7-day view</AlertTitle>
            <AlertDescription>
              Weekly reviews use one complete seven-day period and the seven
              days immediately before it.
            </AlertDescription>
          </Alert>
        ) : error ? (
          <Alert variant="destructive">
            <AlertCircle />
            <AlertTitle>Weekly review unavailable</AlertTitle>
            <AlertDescription>{getWeeklyReviewError(error)}</AlertDescription>
          </Alert>
        ) : isGenerating ? (
          <div className="space-y-4" aria-live="polite">
            <div>
              <p className="font-medium">Reviewing the seven-day snapshot</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Your local model is comparing performance and preparing a
                concise plan. This can take up to a minute.
              </p>
            </div>
            <Skeleton className="h-7 w-2/3" />
            <Skeleton className="h-16 w-full" />
            <div className="grid gap-3 lg:grid-cols-3">
              {Array.from({ length: 3 }, (_, index) => (
                <Skeleton className="h-32" key={index} />
              ))}
            </div>
          </div>
        ) : isLoading ? (
          <div
            aria-label="Loading saved weekly review"
            className="space-y-3"
            role="status"
          >
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : review ? (
          <div className="space-y-5">
            <div>
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge variant="secondary">Local AI · Saved</Badge>
                {review.generation_mode === "automation" ? (
                  <Badge>Automated</Badge>
                ) : null}
                {isStale ? (
                  <Badge
                    className="border-amber-500/40 text-amber-700 dark:text-amber-300"
                    variant="outline"
                  >
                    Trends changed
                  </Badge>
                ) : null}
              </div>
              <h2 className="text-xl font-semibold tracking-tight">
                {review.headline}
              </h2>
              <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
                {review.summary}
              </p>
            </div>

            <div className="grid gap-3 lg:grid-cols-3">
              <WeeklyReviewList
                emptyMessage="No clear wins identified for this period."
                icon={Trophy}
                iconClassName="text-emerald-600 dark:text-emerald-400"
                items={review.wins}
                title="Wins"
              />
              <WeeklyReviewList
                emptyMessage="No specific concerns identified."
                icon={ShieldAlert}
                iconClassName="text-rose-600 dark:text-rose-400"
                items={review.concerns}
                title="Concerns"
              />
              <WeeklyReviewList
                emptyMessage="No priorities were returned."
                icon={ListChecks}
                iconClassName="text-sky-600 dark:text-sky-400"
                items={review.priorities}
                isAdded={(item) => addedPriorities.has(item)}
                isCreating={(item) => creatingAction?.title === item}
                onCreateAction={onCreatePriority}
                title="Next-week priorities"
              />
            </div>

            <p className="text-xs text-muted-foreground">
              Saved from {review.model} on{" "}
              {formatGeneratedAt(review.generated_at)}. Verify important
              decisions against the source trends below
              {isStale ? ", then update this review" : ""}.
            </p>
          </div>
        ) : (
          <div className="flex min-h-40 flex-col items-center justify-center text-center">
            <div className="mb-4 rounded-full bg-violet-500/10 p-4">
              <Sparkles className="size-7 text-violet-600 dark:text-violet-400" />
            </div>
            <p className="font-medium">Turn the week into a focused plan</p>
            <p className="mt-1 max-w-lg text-sm text-muted-foreground">
              OpsPilot sends only this saved trend snapshot to your private,
              locally running AI model.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export const Route = createFileRoute("/_layout/trends")({
  component: Trends,
  head: () => ({
    meta: [{ title: "Operations Trends | OpsPilot" }],
  }),
})

function Trends() {
  const [endDate, setEndDate] = useState(getSydneyDate)
  const [days, setDays] = useState<TrendDays>(7)
  const queryClient = useQueryClient()

  const trendsQuery = useQuery({
    queryKey: ["dashboard-trends", endDate, days],
    queryFn: async () => {
      const response = await DashboardService.readDashboardTrends({
        query: { end_date: endDate || undefined, days },
      })
      return response.data
    },
  })

  const data = trendsQuery.data
  const reviewEndDate = data?.end_date ?? endDate
  const latestReviewQuery = useQuery({
    queryKey: ["ai-weekly-review", reviewEndDate],
    queryFn: async () => {
      const response = await AiService.readLatestWeeklyReview({
        query: { end_date: reviewEndDate || undefined },
      })
      return isWeeklyReview(response.data) ? response.data : null
    },
    enabled: Boolean(data && days === 7),
  })
  const reviewMutation = useMutation({
    mutationFn: async () => {
      const response = await AiService.createWeeklyReview({
        query: { end_date: reviewEndDate || undefined },
      })
      return response.data
    },
    onSuccess: (review) => {
      queryClient.setQueryData(
        ["ai-weekly-review", review.period_end_date],
        review,
      )
      toast.success("Weekly review saved", {
        description: review.headline,
      })
    },
    onError: (error) => {
      toast.error("Weekly review not created", {
        description: getWeeklyReviewError(error),
      })
    },
  })
  const generatedReview =
    reviewMutation.data?.period_end_date === reviewEndDate
      ? reviewMutation.data
      : undefined
  const review =
    days === 7
      ? (generatedReview ?? latestReviewQuery.data ?? undefined)
      : undefined
  const reviewActionsQuery = useQuery({
    queryKey: ["actions", "weekly-review", review?.id],
    queryFn: async () => {
      if (!review) return []
      const response = await ActionsService.readActions({
        query: {
          source_weekly_review_id: review.id,
          skip: 0,
          limit: 100,
        },
      })
      return response.data.data
    },
    enabled: Boolean(review),
  })
  const createActionMutation = useMutation({
    mutationFn: async (payload: ActionItemCreate) => {
      const response = await ActionsService.createAction({ body: payload })
      return response.data
    },
    onSuccess: async (action) => {
      await queryClient.invalidateQueries({ queryKey: ["actions"] })
      toast.success("Added to Action Center", {
        description: action.title,
      })
    },
    onError: (error) => {
      const isDuplicate = isAxiosError(error) && error.response?.status === 409
      toast.error(isDuplicate ? "Action already added" : "Action not created", {
        description: getWeeklyReviewError(error),
      })
    },
  })
  const addedPriorities = new Set(
    (reviewActionsQuery.data ?? []).map(
      (action) => action.source_suggestion ?? action.title,
    ),
  )
  const isReviewStale = Boolean(
    review && data && JSON.stringify(review.source) !== JSON.stringify(data),
  )

  return (
    <div className="space-y-6" data-testid="operations-trends">
      <section className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-emerald-500/15 via-background to-background p-6 shadow-sm md:p-8">
        <div className="absolute -right-20 -top-24 size-72 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="relative flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
          <div className="max-w-2xl">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-emerald-300">
              <TrendingUp className="size-4" />
              OpsPilot performance
            </div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Operations trends
            </h1>
            <p className="mt-3 text-muted-foreground">
              See daily performance in context and compare each period with the
              same number of preceding days.
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Select
              value={String(days)}
              onValueChange={(value) => {
                reviewMutation.reset()
                setDays(Number(value) as TrendDays)
              }}
            >
              <SelectTrigger className="w-full bg-background/80 sm:w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7">7 days</SelectItem>
                <SelectItem value="14">14 days</SelectItem>
                <SelectItem value="30">30 days</SelectItem>
              </SelectContent>
            </Select>
            <div className="relative">
              <CalendarDays className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                aria-label="Trend period end date"
                className="w-full bg-background/80 pl-9 sm:w-44"
                type="date"
                value={endDate}
                onChange={(event) => {
                  reviewMutation.reset()
                  setEndDate(event.target.value)
                }}
              />
            </div>
            <Button
              className="bg-background/80"
              variant="outline"
              disabled={trendsQuery.isFetching}
              onClick={() => {
                reviewMutation.reset()
                void trendsQuery.refetch()
                if (days === 7) void latestReviewQuery.refetch()
              }}
            >
              {trendsQuery.isFetching ? (
                <LoaderCircle className="animate-spin" />
              ) : (
                <RefreshCw />
              )}
              Refresh
            </Button>
          </div>
        </div>
      </section>

      {trendsQuery.error ? (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>Trends unavailable</AlertTitle>
          <AlertDescription>
            {getErrorMessage(trendsQuery.error)}
          </AlertDescription>
        </Alert>
      ) : null}

      {trendsQuery.isPending || !data ? (
        <div className="space-y-6" role="status">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, index) => (
              <Skeleton className="h-36 rounded-xl" key={index} />
            ))}
          </div>
          <Skeleton className="h-96 rounded-xl" />
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="font-medium">
                {formatDate(data.start_date)} – {formatDate(data.end_date)}
              </p>
              <p className="text-xs text-muted-foreground">
                {data.days}-day period · {data.timezone}
              </p>
            </div>
            <Badge variant="outline">
              Compared with{" "}
              {formatDate(data.previous_period.start_date, "short")}
              {" – "}
              {formatDate(data.previous_period.end_date, "short")}
            </Badge>
          </div>

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <TrendMetric
              label="Revenue"
              value={formatCurrency(data.revenue)}
              change={data.previous_period.revenue_change_percent}
              icon={CircleDollarSign}
              iconClassName="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
            />
            <TrendMetric
              label="Sales"
              value={data.sales_count.toLocaleString("en-AU")}
              change={data.previous_period.sales_count_change_percent}
              icon={ReceiptText}
              iconClassName="bg-sky-500/10 text-sky-600 dark:text-sky-400"
            />
            <TrendMetric
              label="Units sold"
              value={formatQuantity(data.units_sold)}
              change={data.previous_period.units_sold_change_percent}
              icon={ShoppingBasket}
              iconClassName="bg-violet-500/10 text-violet-600 dark:text-violet-400"
            />
            <TrendMetric
              label="Average sale"
              value={formatCurrency(data.average_sale_value)}
              icon={TrendingUp}
              iconClassName="bg-amber-500/10 text-amber-600 dark:text-amber-400"
            />
          </section>

          <WeeklyReview
            addedPriorities={addedPriorities}
            canGenerate={days === 7}
            creatingAction={
              createActionMutation.isPending
                ? createActionMutation.variables
                : undefined
            }
            error={reviewMutation.error ?? latestReviewQuery.error}
            isGenerating={reviewMutation.isPending}
            isLoading={latestReviewQuery.isPending && days === 7}
            isStale={isReviewStale}
            onGenerate={() => reviewMutation.mutate()}
            onCreatePriority={(priority) => {
              if (!review) return
              createActionMutation.mutate({
                title: priority,
                category: "priority",
                priority: "medium",
                source_weekly_review_id: review.id,
                source_suggestion: priority,
              })
            }}
            review={review}
          />

          <Card>
            <CardHeader className="border-b">
              <CardTitle>Daily revenue</CardTitle>
              <CardDescription>
                Revenue recorded on each business day in the selected period.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-4">
              <RevenueChart daily={data.daily} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b">
              <CardTitle>Daily performance</CardTitle>
              <CardDescription>
                The deterministic daily values behind the chart and period
                totals.
              </CardDescription>
            </CardHeader>
            <CardContent>
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
                    {data.daily.map((day) => (
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
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
