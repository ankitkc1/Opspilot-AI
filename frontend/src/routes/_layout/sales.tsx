import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import {
  AlertTriangle,
  CircleDollarSign,
  LoaderCircle,
  PackageCheck,
  Plus,
  ReceiptText,
  ShoppingCart,
  Trash2,
  TrendingUp,
} from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { client } from "@/client/client.gen"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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

type Product = {
  id: string
  name: string
  category: string
  selling_price: string | number
  unit: string
  is_active: boolean
  track_inventory: boolean
}

type InventoryBalance = {
  product_id: string
  product_name: string
  unit: string
  is_active: boolean
  track_inventory: boolean
  reorder_level: string | number
  quantity_on_hand: string | number
  is_low_stock: boolean
}

type SaleItem = {
  id: string
  sale_id: string
  product_id: string
  quantity: string | number
  unit_price: string | number
  line_total: string | number
}

type Sale = {
  id: string
  sold_at: string
  total_amount: string | number
  created_at: string
  items: SaleItem[]
}

type ProductsResponse = {
  data: Product[]
  count: number
}

type InventoryBalancesResponse = {
  data: InventoryBalance[]
  count: number
}

type SalesResponse = {
  data: Sale[]
  count: number
}

type SaleLineForm = {
  key: string
  product_id: string
  quantity: string
}

type SalePayload = {
  sold_at: string
  items: Array<{
    product_id: string
    quantity: string
  }>
}

const salesQueryKey = ["sales"] as const

const currencyFormatter = new Intl.NumberFormat("en-AU", {
  style: "currency",
  currency: "AUD",
})

const quantityFormatter = new Intl.NumberFormat("en-AU", {
  maximumFractionDigits: 3,
})

function currentLocalDateTime(): string {
  const date = new Date()
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16)
}

function newSaleLine(): SaleLineForm {
  return {
    key: `${Date.now()}-${Math.random()}`,
    product_id: "",
    quantity: "1",
  }
}

async function readProducts(): Promise<ProductsResponse> {
  const response = await client.get<{ 200: ProductsResponse }, never, true>({
    url: "/api/v1/products/",
    query: { skip: 0, limit: 100 },
    security: [{ scheme: "bearer", type: "http" }],
    responseType: "json",
    throwOnError: true,
  })
  return response.data
}

async function readBalances(): Promise<InventoryBalancesResponse> {
  const response = await client.get<
    { 200: InventoryBalancesResponse },
    never,
    true
  >({
    url: "/api/v1/inventory/balances/",
    query: { skip: 0, limit: 100 },
    security: [{ scheme: "bearer", type: "http" }],
    responseType: "json",
    throwOnError: true,
  })
  return response.data
}

async function readSales(): Promise<SalesResponse> {
  const response = await client.get<{ 200: SalesResponse }, never, true>({
    url: "/api/v1/sales/",
    query: { skip: 0, limit: 100 },
    security: [{ scheme: "bearer", type: "http" }],
    responseType: "json",
    throwOnError: true,
  })
  return response.data
}

async function readSalesPage() {
  const [sales, products, balances] = await Promise.all([
    readSales(),
    readProducts(),
    readBalances(),
  ])
  return { sales, products, balances }
}

async function createSale(payload: SalePayload): Promise<Sale> {
  const response = await client.post<{ 201: Sale }, never, true>({
    url: "/api/v1/sales/",
    body: payload,
    security: [{ scheme: "bearer", type: "http" }],
    responseType: "json",
    throwOnError: true,
  })
  return response.data
}

function getErrorMessage(error: unknown): string {
  if (!isAxiosError(error)) {
    return "The request could not be completed. Please try again."
  }

  const detail = (error.response?.data as { detail?: unknown } | undefined)
    ?.detail
  if (typeof detail === "string") {
    return detail
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        typeof item === "object" && item !== null && "msg" in item
          ? String(item.msg)
          : null,
      )
      .filter(Boolean)
    if (messages.length > 0) {
      return messages.join(" ")
    }
  }
  if (typeof detail === "object" && detail !== null && "message" in detail) {
    const stockDetail = detail as {
      message: unknown
      available?: unknown
      requested?: unknown
    }
    const quantities =
      stockDetail.available !== undefined && stockDetail.requested !== undefined
        ? ` Available: ${stockDetail.available}; requested: ${stockDetail.requested}.`
        : ""
    return `${String(stockDetail.message)}.${quantities}`
  }
  return "The request could not be completed. Please try again."
}

function validateSale(
  lines: SaleLineForm[],
  soldAt: string,
  products: Product[],
  balances: InventoryBalance[],
): string | null {
  if (!soldAt) {
    return "Choose when the sale occurred."
  }
  if (lines.length === 0) {
    return "Add at least one product."
  }

  const productIds = new Set<string>()
  for (const line of lines) {
    if (!line.product_id) {
      return "Select a product for every sale line."
    }
    if (productIds.has(line.product_id)) {
      return "Each product can appear only once. Update its quantity instead."
    }
    productIds.add(line.product_id)

    const quantity = Number(line.quantity)
    if (!Number.isFinite(quantity) || quantity <= 0) {
      return "Every quantity must be greater than zero."
    }

    const product = products.find((item) => item.id === line.product_id)
    if (!product?.is_active) {
      return "One of the selected products is no longer active."
    }
    if (product.track_inventory) {
      const balance = balances.find((item) => item.product_id === product.id)
      const available = Number(balance?.quantity_on_hand ?? 0)
      if (quantity > available) {
        return `${product.name} has ${quantityFormatter.format(
          available,
        )} ${product.unit} available.`
      }
    }
  }

  return null
}

export const Route = createFileRoute("/_layout/sales")({
  component: Sales,
  head: () => ({
    meta: [{ title: "Sales | OpsPilot" }],
  }),
})

type SaleEditorProps = {
  open: boolean
  products: Product[]
  balances: InventoryBalance[]
  onOpenChange: (open: boolean) => void
}

function SaleEditor({
  open,
  products,
  balances,
  onOpenChange,
}: SaleEditorProps) {
  const queryClient = useQueryClient()
  const [soldAt, setSoldAt] = useState(currentLocalDateTime)
  const [lines, setLines] = useState<SaleLineForm[]>(() => [newSaleLine()])
  const [formError, setFormError] = useState<string | null>(null)
  const activeProducts = products.filter((product) => product.is_active)
  const productsById = useMemo(
    () => new Map(products.map((product) => [product.id, product])),
    [products],
  )
  const balancesByProduct = useMemo(
    () => new Map(balances.map((balance) => [balance.product_id, balance])),
    [balances],
  )

  useEffect(() => {
    if (open) {
      setSoldAt(currentLocalDateTime())
      setLines([newSaleLine()])
      setFormError(null)
    }
  }, [open])

  const mutation = useMutation({
    mutationFn: createSale,
    onSuccess: async (sale) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: salesQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["inventory"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      ])
      toast.success("Sale recorded", {
        description: `${currencyFormatter.format(
          Number(sale.total_amount),
        )} across ${sale.items.length} product${
          sale.items.length === 1 ? "" : "s"
        }.`,
      })
      onOpenChange(false)
    },
    onError: (error) => setFormError(getErrorMessage(error)),
  })

  const updateLine = (
    key: string,
    field: "product_id" | "quantity",
    value: string,
  ) => {
    setLines((current) =>
      current.map((line) =>
        line.key === key ? { ...line, [field]: value } : line,
      ),
    )
  }

  const removeLine = (key: string) => {
    setLines((current) => current.filter((line) => line.key !== key))
  }

  const estimatedTotal = lines.reduce((total, line) => {
    const product = productsById.get(line.product_id)
    const quantity = Number(line.quantity)
    if (!product || !Number.isFinite(quantity)) {
      return total
    }
    return total + Number(product.selling_price) * quantity
  }, 0)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validationError = validateSale(lines, soldAt, products, balances)
    if (validationError) {
      setFormError(validationError)
      return
    }

    setFormError(null)
    mutation.mutate({
      sold_at: new Date(soldAt).toISOString(),
      items: lines.map((line) => ({
        product_id: line.product_id,
        quantity: Number(line.quantity).toFixed(3),
      })),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
        <form onSubmit={handleSubmit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>Record sale</DialogTitle>
            <DialogDescription>
              Prices come from the product catalogue and stock is deducted on
              submission.
            </DialogDescription>
          </DialogHeader>

          {formError ? (
            <Alert variant="destructive">
              <AlertTitle>Sale not recorded</AlertTitle>
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}

          {activeProducts.length === 0 ? (
            <Alert>
              <AlertTriangle />
              <AlertTitle>No active products</AlertTitle>
              <AlertDescription>
                Create or activate a product before recording a sale.
              </AlertDescription>
            </Alert>
          ) : (
            <>
              <div className="max-w-xs space-y-2">
                <Label htmlFor="sale-time">Sold at</Label>
                <Input
                  id="sale-time"
                  type="datetime-local"
                  value={soldAt}
                  onChange={(event) => setSoldAt(event.target.value)}
                />
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Products</Label>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      setLines((current) => [...current, newSaleLine()])
                    }
                    disabled={lines.length >= activeProducts.length}
                  >
                    <Plus />
                    Add line
                  </Button>
                </div>

                {lines.map((line, index) => {
                  const product = productsById.get(line.product_id)
                  const balance = balancesByProduct.get(line.product_id)
                  const lineTotal =
                    Number(product?.selling_price ?? 0) *
                    Number(line.quantity || 0)
                  const selectedElsewhere = new Set(
                    lines
                      .filter((item) => item.key !== line.key)
                      .map((item) => item.product_id),
                  )

                  return (
                    <div
                      key={line.key}
                      className="grid gap-3 rounded-xl border bg-muted/20 p-4 md:grid-cols-[minmax(0,1fr)_8rem_8rem_auto] md:items-end"
                    >
                      <div className="space-y-2">
                        <Label htmlFor={`sale-product-${line.key}`}>
                          Product {index + 1}
                        </Label>
                        <select
                          id={`sale-product-${line.key}`}
                          className="border-input bg-background focus-visible:border-ring focus-visible:ring-ring/50 h-9 w-full rounded-md border px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
                          value={line.product_id}
                          onChange={(event) =>
                            updateLine(
                              line.key,
                              "product_id",
                              event.target.value,
                            )
                          }
                        >
                          <option value="">Select a product</option>
                          {activeProducts.map((item) => (
                            <option
                              key={item.id}
                              value={item.id}
                              disabled={selectedElsewhere.has(item.id)}
                            >
                              {item.name} ·{" "}
                              {currencyFormatter.format(
                                Number(item.selling_price),
                              )}
                            </option>
                          ))}
                        </select>
                        {product ? (
                          <p className="text-xs text-muted-foreground">
                            {product.track_inventory
                              ? `${quantityFormatter.format(
                                  Number(balance?.quantity_on_hand ?? 0),
                                )} ${product.unit} available`
                              : "Inventory not tracked"}
                          </p>
                        ) : null}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor={`sale-quantity-${line.key}`}>
                          Quantity
                        </Label>
                        <Input
                          id={`sale-quantity-${line.key}`}
                          type="number"
                          min="0.001"
                          step="0.001"
                          inputMode="decimal"
                          value={line.quantity}
                          onChange={(event) =>
                            updateLine(line.key, "quantity", event.target.value)
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Line total</Label>
                        <div className="flex h-9 items-center font-semibold tabular-nums">
                          {currencyFormatter.format(lineTotal)}
                        </div>
                      </div>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        aria-label={`Remove product ${index + 1}`}
                        onClick={() => removeLine(line.key)}
                        disabled={lines.length === 1}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  )
                })}
              </div>

              <div className="flex items-center justify-between rounded-xl bg-primary/10 px-5 py-4">
                <div>
                  <p className="text-sm font-medium">Estimated total</p>
                  <p className="text-xs text-muted-foreground">
                    The API confirms and stores the final total.
                  </p>
                </div>
                <p className="text-2xl font-semibold tabular-nums">
                  {currencyFormatter.format(estimatedTotal)}
                </p>
              </div>
            </>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={mutation.isPending || activeProducts.length === 0}
            >
              {mutation.isPending ? (
                <LoaderCircle className="animate-spin" />
              ) : (
                <ReceiptText />
              )}
              Complete sale
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function SalesSkeleton() {
  return (
    <div className="space-y-5" aria-label="Loading sales" role="status">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-96 rounded-xl" />
    </div>
  )
}

function Sales() {
  const [editorOpen, setEditorOpen] = useState(false)
  const { data, error, isPending } = useQuery({
    queryKey: salesQueryKey,
    queryFn: readSalesPage,
  })

  const sales = data?.sales.data ?? []
  const products = data?.products.data ?? []
  const balances = data?.balances.data ?? []
  const productNames = useMemo(
    () => new Map(products.map((product) => [product.id, product.name])),
    [products],
  )

  const recentRevenue = sales.reduce(
    (total, sale) => total + Number(sale.total_amount),
    0,
  )
  const recentUnits = sales.reduce(
    (total, sale) =>
      total +
      sale.items.reduce(
        (saleUnits, item) => saleUnits + Number(item.quantity),
        0,
      ),
    0,
  )
  const averageSale = sales.length > 0 ? recentRevenue / sales.length : 0

  return (
    <div className="space-y-6" data-testid="sales-page">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-primary">
            <ShoppingCart className="size-4" />
            Sales operations
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">Sales</h1>
          <p className="mt-1 text-muted-foreground">
            Record transactions and review recent sales activity.
          </p>
        </div>
        <Button onClick={() => setEditorOpen(true)}>
          <Plus />
          New sale
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Sales unavailable</AlertTitle>
          <AlertDescription>{getErrorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}

      {isPending ? (
        <SalesSkeleton />
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              {
                label: "Total sales",
                value: (data?.sales.count ?? sales.length).toLocaleString(
                  "en-AU",
                ),
                helper: "All recorded transactions",
                icon: ReceiptText,
                color: "bg-primary/10 text-primary",
              },
              {
                label: "Recent revenue",
                value: currencyFormatter.format(recentRevenue),
                helper: "From the latest loaded sales",
                icon: CircleDollarSign,
                color:
                  "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
              },
              {
                label: "Average sale",
                value: currencyFormatter.format(averageSale),
                helper: "Across recent transactions",
                icon: TrendingUp,
                color: "bg-violet-500/10 text-violet-600 dark:text-violet-400",
              },
              {
                label: "Units sold",
                value: quantityFormatter.format(recentUnits),
                helper: "Across recent sale lines",
                icon: PackageCheck,
                color: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
              },
            ].map((metric) => (
              <Card key={metric.label} className="py-5">
                <CardContent className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm text-muted-foreground">
                      {metric.label}
                    </p>
                    <p className="mt-1 truncate text-2xl font-semibold tabular-nums">
                      {metric.value}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {metric.helper}
                    </p>
                  </div>
                  <div className={cn("rounded-xl p-3", metric.color)}>
                    <metric.icon className="size-5" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </section>

          <Card>
            <CardHeader className="border-b">
              <CardTitle>Sales history</CardTitle>
              <p className="text-sm text-muted-foreground">
                Newest transactions appear first
              </p>
            </CardHeader>
            <CardContent>
              {sales.length === 0 ? (
                <div className="flex min-h-64 flex-col items-center justify-center text-center">
                  <div className="mb-4 rounded-full bg-muted p-4">
                    <ReceiptText className="size-8 text-muted-foreground" />
                  </div>
                  <h2 className="text-lg font-semibold">No sales recorded</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Record the first sale to populate your dashboard and stock
                    history.
                  </p>
                  <Button className="mt-5" onClick={() => setEditorOpen(true)}>
                    <Plus />
                    New sale
                  </Button>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Sold at</TableHead>
                      <TableHead>Products</TableHead>
                      <TableHead>Units</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sales.map((sale) => {
                      const unitCount = sale.items.reduce(
                        (total, item) => total + Number(item.quantity),
                        0,
                      )
                      return (
                        <TableRow key={sale.id}>
                          <TableCell>
                            <div>
                              <p className="font-medium">
                                {new Intl.DateTimeFormat("en-AU", {
                                  dateStyle: "medium",
                                  timeStyle: "short",
                                }).format(new Date(sale.sold_at))}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                #{sale.id.slice(0, 8)}
                              </p>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="max-w-md space-y-1">
                              {sale.items.map((item) => (
                                <p key={item.id} className="truncate text-sm">
                                  {productNames.get(item.product_id) ??
                                    "Unknown product"}
                                  <span className="text-muted-foreground">
                                    {" "}
                                    ×{" "}
                                    {quantityFormatter.format(
                                      Number(item.quantity),
                                    )}
                                  </span>
                                </p>
                              ))}
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">
                              {quantityFormatter.format(unitCount)}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-semibold tabular-nums">
                            {currencyFormatter.format(
                              Number(sale.total_amount),
                            )}
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <SaleEditor
        open={editorOpen}
        products={products}
        balances={balances}
        onOpenChange={setEditorOpen}
      />
    </div>
  )
}
