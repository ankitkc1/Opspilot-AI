import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import type { LucideIcon } from "lucide-react"
import {
  AlertCircle,
  CalendarDays,
  DollarSign,
  PackageCheck,
  PackageSearch,
  ReceiptText,
  RefreshCw,
  ShoppingBasket,
  TrendingUp,
  Trophy,
} from "lucide-react"
import { useState } from "react"

import { client } from "@/client/client.gen"
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
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

type TopProduct = {
  product_id: string
  product_name: string
  quantity_sold: string
  revenue: string
}

type LowStockItem = {
  product_id: string
  product_name: string
  unit: string
  reorder_level: string
  quantity_on_hand: string
  is_low_stock: boolean
}

type DashboardSummary = {
  report_date: string
  timezone: string
  revenue: string
  sales_count: number
  units_sold: string
  average_sale_value: string
  top_products: TopProduct[]
  low_stock_count: number
  low_stock: LowStockItem[]
}

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

function formatReportDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number)
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "full" }).format(
    new Date(year, month - 1, day),
  )
}

function formatCurrency(value: string): string {
  return currencyFormatter.format(Number(value))
}

function formatQuantity(value: string): string {
  return quantityFormatter.format(Number(value))
}

async function getDashboardSummary(
  reportDate: string,
): Promise<DashboardSummary> {
  const response = await client.get<{ 200: DashboardSummary }, never, true>({
    url: "/api/v1/dashboard/summary/",
    query: {
      report_date: reportDate,
      top_limit: 5,
      low_stock_limit: 8,
    },
    security: [{ scheme: "bearer", type: "http" }],
    responseType: "json",
    throwOnError: true,
  })
  return response.data
}

type MetricCardProps = {
  label: string
  value: string
  helper: string
  icon: LucideIcon
  iconClassName: string
}

function MetricCard({
  label,
  value,
  helper,
  icon: Icon,
  iconClassName,
}: MetricCardProps) {
  return (
    <Card className="gap-4 overflow-hidden py-5">
      <CardContent className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="mt-2 truncate text-3xl font-semibold tracking-tight">
            {value}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{helper}</p>
        </div>
        <div className={cn("rounded-xl p-3", iconClassName)}>
          <Icon className="size-5" />
        </div>
      </CardContent>
    </Card>
  )
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-label="Loading dashboard" role="status">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-36 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
        <Skeleton className="h-96 rounded-xl" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
    </div>
  )
}

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Operations Dashboard | OpsPilot",
      },
    ],
  }),
})

function Dashboard() {
  const [reportDate, setReportDate] = useState(getSydneyDate)
  const { data, error, isFetching, isPending, refetch } = useQuery({
    queryKey: ["dashboard-summary", reportDate],
    queryFn: () => getDashboardSummary(reportDate),
  })

  const maxProductRevenue = Math.max(
    ...(data?.top_products ?? []).map((product) => Number(product.revenue)),
    1,
  )

  return (
    <div className="space-y-6" data-testid="operations-dashboard">
      <section className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-primary/15 via-background to-background p-6 shadow-sm md:p-8">
        <div className="absolute -right-20 -top-24 size-72 rounded-full bg-primary/10 blur-3xl" />
        <div className="relative flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
          <div className="max-w-2xl">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-primary">
              <TrendingUp className="size-4" />
              OpsPilot operations
            </div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Daily operations at a glance
            </h1>
            <p className="mt-3 max-w-xl text-muted-foreground">
              Revenue, sales performance, product momentum, and stock risk in
              one focused view.
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative block">
              <CalendarDays className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                aria-label="Dashboard report date"
                className="w-full bg-background/80 pl-9 sm:w-44"
                type="date"
                value={reportDate}
                onChange={(event) => setReportDate(event.target.value)}
              />
            </div>
            <Button
              variant="outline"
              className="bg-background/80"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={cn(isFetching && "animate-spin")} />
              Refresh
            </Button>
          </div>
        </div>
      </section>

      {error ? (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>Dashboard unavailable</AlertTitle>
          <AlertDescription>
            We couldn't load the operations summary. Check that the API is
            running, then try again.
          </AlertDescription>
        </Alert>
      ) : null}

      {isPending || !data ? (
        <DashboardSkeleton />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="font-medium">
                {formatReportDate(data.report_date)}
              </p>
              <p className="text-xs text-muted-foreground">
                Business day · {data.timezone}
              </p>
            </div>
            {isFetching ? (
              <Badge variant="secondary">Updating</Badge>
            ) : (
              <Badge variant="outline">Up to date</Badge>
            )}
          </div>

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Revenue"
              value={formatCurrency(data.revenue)}
              helper="Gross sales for the day"
              icon={DollarSign}
              iconClassName="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
            />
            <MetricCard
              label="Sales"
              value={data.sales_count.toLocaleString("en-AU")}
              helper="Completed transactions"
              icon={ReceiptText}
              iconClassName="bg-sky-500/10 text-sky-600 dark:text-sky-400"
            />
            <MetricCard
              label="Units sold"
              value={formatQuantity(data.units_sold)}
              helper="Across all products"
              icon={ShoppingBasket}
              iconClassName="bg-violet-500/10 text-violet-600 dark:text-violet-400"
            />
            <MetricCard
              label="Average sale"
              value={formatCurrency(data.average_sale_value)}
              helper="Revenue per transaction"
              icon={TrendingUp}
              iconClassName="bg-amber-500/10 text-amber-600 dark:text-amber-400"
            />
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
            <Card>
              <CardHeader className="border-b">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-amber-500/10 p-2 text-amber-600 dark:text-amber-400">
                    <Trophy className="size-5" />
                  </div>
                  <div>
                    <CardTitle>Top products</CardTitle>
                    <CardDescription>
                      Ranked by revenue for the selected day
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {data.top_products.length === 0 ? (
                  <div className="flex min-h-64 flex-col items-center justify-center text-center">
                    <div className="mb-4 rounded-full bg-muted p-4">
                      <PackageSearch className="size-7 text-muted-foreground" />
                    </div>
                    <p className="font-medium">No sales recorded</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Product performance will appear after the first sale.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-5">
                    {data.top_products.map((product, index) => (
                      <div key={product.product_id} className="space-y-2">
                        <div className="flex items-center gap-3">
                          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">
                            {index + 1}
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-3">
                              <p className="truncate text-sm font-medium">
                                {product.product_name}
                              </p>
                              <p className="text-sm font-semibold tabular-nums">
                                {formatCurrency(product.revenue)}
                              </p>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {formatQuantity(product.quantity_sold)} units sold
                            </p>
                          </div>
                        </div>
                        <div className="ml-10 h-1.5 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-primary transition-all"
                            style={{
                              width: `${Math.max(
                                5,
                                (Number(product.revenue) / maxProductRevenue) *
                                  100,
                              )}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="border-b">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-rose-500/10 p-2 text-rose-600 dark:text-rose-400">
                      <PackageSearch className="size-5" />
                    </div>
                    <div>
                      <CardTitle>Low stock</CardTitle>
                      <CardDescription>
                        Products requiring attention now
                      </CardDescription>
                    </div>
                  </div>
                  <Badge
                    variant={
                      data.low_stock_count > 0 ? "destructive" : "secondary"
                    }
                  >
                    {data.low_stock_count}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                {data.low_stock.length === 0 ? (
                  <div className="flex min-h-64 flex-col items-center justify-center text-center">
                    <div className="mb-4 rounded-full bg-emerald-500/10 p-4">
                      <PackageCheck className="size-7 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <p className="font-medium">Stock levels look healthy</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      No tracked products are below their reorder level.
                    </p>
                  </div>
                ) : (
                  <div className="divide-y">
                    {data.low_stock.map((item) => {
                      const quantity = Number(item.quantity_on_hand)
                      return (
                        <div
                          key={item.product_id}
                          className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium">
                              {item.product_name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              Reorder at {formatQuantity(item.reorder_level)}{" "}
                              {item.unit}
                            </p>
                          </div>
                          <div className="text-right">
                            <p
                              className={cn(
                                "text-sm font-semibold tabular-nums",
                                quantity <= 0
                                  ? "text-destructive"
                                  : "text-amber-600 dark:text-amber-400",
                              )}
                            >
                              {formatQuantity(item.quantity_on_hand)}{" "}
                              {item.unit}
                            </p>
                            <Badge
                              className="mt-1"
                              variant={
                                quantity <= 0 ? "destructive" : "outline"
                              }
                            >
                              {quantity <= 0 ? "Out of stock" : "Reorder"}
                            </Badge>
                          </div>
                        </div>
                      )
                    })}
                    {data.low_stock_count > data.low_stock.length ? (
                      <p className="pt-4 text-center text-xs text-muted-foreground">
                        Showing {data.low_stock.length} of{" "}
                        {data.low_stock_count} low-stock products
                      </p>
                    ) : null}
                  </div>
                )}
              </CardContent>
            </Card>
          </section>
        </>
      )}
    </div>
  )
}
