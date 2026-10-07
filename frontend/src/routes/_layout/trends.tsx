import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import type { LucideIcon } from "lucide-react"
import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  CalendarDays,
  CircleDollarSign,
  LoaderCircle,
  Minus,
  ReceiptText,
  RefreshCw,
  ShoppingBasket,
  TrendingUp,
} from "lucide-react"
import { useState } from "react"

import {
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

export const Route = createFileRoute("/_layout/trends")({
  component: Trends,
  head: () => ({
    meta: [{ title: "Operations Trends | OpsPilot" }],
  }),
})

function Trends() {
  const [endDate, setEndDate] = useState(getSydneyDate)
  const [days, setDays] = useState<TrendDays>(7)

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
              onValueChange={(value) => setDays(Number(value) as TrendDays)}
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
                onChange={(event) => setEndDate(event.target.value)}
              />
            </div>
            <Button
              className="bg-background/80"
              variant="outline"
              disabled={trendsQuery.isFetching}
              onClick={() => void trendsQuery.refetch()}
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
