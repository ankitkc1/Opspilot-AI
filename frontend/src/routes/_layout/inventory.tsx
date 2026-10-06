import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import {
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  Boxes,
  ClipboardPlus,
  History,
  LoaderCircle,
  PackageCheck,
  PackageX,
  Search,
  SlidersHorizontal,
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

type InventoryMovement = {
  id: string
  product_id: string
  sale_id: string | null
  movement_type: "opening" | "receipt" | "adjustment" | "sale"
  quantity_delta: string | number
  occurred_at: string
  note: string | null
  created_at: string
}

type InventoryBalancesResponse = {
  data: InventoryBalance[]
  count: number
}

type InventoryMovementsResponse = {
  data: InventoryMovement[]
  count: number
}

type MovementType = "opening" | "receipt" | "adjustment"
type BalanceFilter = "all" | "low" | "out" | "untracked"

type MovementFormState = {
  product_id: string
  movement_type: MovementType
  quantity_delta: string
  occurred_at: string
  note: string
}

type MovementPayload = {
  product_id: string
  movement_type: MovementType
  quantity_delta: string
  occurred_at: string
  note?: string
}

const inventoryQueryKey = ["inventory"] as const

function currentLocalDateTime(): string {
  const date = new Date()
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16)
}

function emptyMovement(productId = ""): MovementFormState {
  return {
    product_id: productId,
    movement_type: "receipt",
    quantity_delta: "",
    occurred_at: currentLocalDateTime(),
    note: "",
  }
}

const quantityFormatter = new Intl.NumberFormat("en-AU", {
  maximumFractionDigits: 3,
})

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

async function readMovements(): Promise<InventoryMovementsResponse> {
  const response = await client.get<
    { 200: InventoryMovementsResponse },
    never,
    true
  >({
    url: "/api/v1/inventory/movements/",
    query: { skip: 0, limit: 100 },
    security: [{ scheme: "bearer", type: "http" }],
    responseType: "json",
    throwOnError: true,
  })
  return response.data
}

async function readInventory() {
  const [balances, movements] = await Promise.all([
    readBalances(),
    readMovements(),
  ])
  return { balances, movements }
}

async function createMovement(
  payload: MovementPayload,
): Promise<InventoryMovement> {
  const response = await client.post<{ 201: InventoryMovement }, never, true>({
    url: "/api/v1/inventory/movements/",
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
  return "The request could not be completed. Please try again."
}

function movementLabel(type: InventoryMovement["movement_type"]): string {
  return {
    opening: "Opening balance",
    receipt: "Stock receipt",
    adjustment: "Adjustment",
    sale: "Sale",
  }[type]
}

function movementIcon(type: InventoryMovement["movement_type"]) {
  if (type === "receipt" || type === "opening") {
    return ArrowDownToLine
  }
  if (type === "sale") {
    return ArrowUpFromLine
  }
  return SlidersHorizontal
}

function validateMovement(form: MovementFormState): string | null {
  if (!form.product_id) {
    return "Select a product."
  }

  const quantity = Number(form.quantity_delta)
  if (!Number.isFinite(quantity) || quantity === 0) {
    return "Quantity must be a non-zero number."
  }
  if (form.movement_type !== "adjustment" && quantity < 0) {
    return "Opening balances and receipts must use a positive quantity."
  }
  if (!form.occurred_at) {
    return "Choose when the stock movement occurred."
  }
  return null
}

export const Route = createFileRoute("/_layout/inventory")({
  component: Inventory,
  head: () => ({
    meta: [{ title: "Inventory | OpsPilot" }],
  }),
})

type MovementEditorProps = {
  open: boolean
  balances: InventoryBalance[]
  initialProductId: string
  onOpenChange: (open: boolean) => void
}

function MovementEditor({
  open,
  balances,
  initialProductId,
  onOpenChange,
}: MovementEditorProps) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<MovementFormState>(() =>
    emptyMovement(initialProductId),
  )
  const [formError, setFormError] = useState<string | null>(null)
  const trackedProducts = balances.filter(
    (balance) => balance.track_inventory && balance.is_active,
  )

  useEffect(() => {
    if (open) {
      setForm(emptyMovement(initialProductId))
      setFormError(null)
    }
  }, [initialProductId, open])

  const mutation = useMutation({
    mutationFn: createMovement,
    onSuccess: async (movement) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: inventoryQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      ])
      const product = balances.find(
        (balance) => balance.product_id === movement.product_id,
      )
      toast.success("Inventory updated", {
        description: `${product?.product_name ?? "Product"}: ${movementLabel(
          movement.movement_type,
        ).toLocaleLowerCase()}.`,
      })
      onOpenChange(false)
    },
    onError: (error) => setFormError(getErrorMessage(error)),
  })

  const setField = <Key extends keyof MovementFormState>(
    key: Key,
    value: MovementFormState[Key],
  ) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validationError = validateMovement(form)
    if (validationError) {
      setFormError(validationError)
      return
    }

    setFormError(null)
    mutation.mutate({
      product_id: form.product_id,
      movement_type: form.movement_type,
      quantity_delta: Number(form.quantity_delta).toFixed(3),
      occurred_at: new Date(form.occurred_at).toISOString(),
      ...(form.note.trim() ? { note: form.note.trim() } : {}),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>Record stock movement</DialogTitle>
            <DialogDescription>
              Add opening stock, a supplier receipt, or a signed correction.
            </DialogDescription>
          </DialogHeader>

          {formError ? (
            <Alert variant="destructive">
              <AlertTitle>Movement not recorded</AlertTitle>
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}

          {trackedProducts.length === 0 ? (
            <Alert>
              <AlertTriangle />
              <AlertTitle>No tracked products</AlertTitle>
              <AlertDescription>
                Enable inventory tracking on a product before recording stock.
              </AlertDescription>
            </Alert>
          ) : (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="movement-product">Product</Label>
                <select
                  id="movement-product"
                  className="border-input bg-background focus-visible:border-ring focus-visible:ring-ring/50 h-9 w-full rounded-md border px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
                  value={form.product_id}
                  onChange={(event) =>
                    setField("product_id", event.target.value)
                  }
                >
                  <option value="">Select a product</option>
                  {trackedProducts.map((product) => (
                    <option key={product.product_id} value={product.product_id}>
                      {product.product_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="movement-type">Movement type</Label>
                <select
                  id="movement-type"
                  className="border-input bg-background focus-visible:border-ring focus-visible:ring-ring/50 h-9 w-full rounded-md border px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
                  value={form.movement_type}
                  onChange={(event) =>
                    setField(
                      "movement_type",
                      event.target.value as MovementType,
                    )
                  }
                >
                  <option value="opening">Opening balance</option>
                  <option value="receipt">Stock receipt</option>
                  <option value="adjustment">Manual adjustment</option>
                </select>
                <p className="text-xs text-muted-foreground">
                  {form.movement_type === "opening"
                    ? "Use once when bringing an existing stock count into OpsPilot."
                    : form.movement_type === "receipt"
                      ? "Use a positive quantity for stock received from a supplier."
                      : "Use a positive quantity to add stock or a negative quantity to remove it."}
                </p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="movement-quantity">Quantity</Label>
                  <Input
                    id="movement-quantity"
                    type="number"
                    step="0.001"
                    inputMode="decimal"
                    value={form.quantity_delta}
                    onChange={(event) =>
                      setField("quantity_delta", event.target.value)
                    }
                    placeholder={
                      form.movement_type === "adjustment" ? "-2.000" : "10.000"
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="movement-time">Occurred at</Label>
                  <Input
                    id="movement-time"
                    type="datetime-local"
                    value={form.occurred_at}
                    onChange={(event) =>
                      setField("occurred_at", event.target.value)
                    }
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="movement-note">Note (optional)</Label>
                <Input
                  id="movement-note"
                  value={form.note}
                  onChange={(event) => setField("note", event.target.value)}
                  placeholder="Supplier delivery or stocktake correction"
                  maxLength={255}
                />
              </div>
            </div>
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
              disabled={mutation.isPending || trackedProducts.length === 0}
            >
              {mutation.isPending ? (
                <LoaderCircle className="animate-spin" />
              ) : (
                <ClipboardPlus />
              )}
              Record movement
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function InventorySkeleton() {
  return (
    <div className="space-y-5" aria-label="Loading inventory" role="status">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-96 rounded-xl" />
    </div>
  )
}

function Inventory() {
  const [search, setSearch] = useState("")
  const [balanceFilter, setBalanceFilter] = useState<BalanceFilter>("all")
  const [movementFilter, setMovementFilter] = useState("")
  const [editorOpen, setEditorOpen] = useState(false)
  const [initialProductId, setInitialProductId] = useState("")

  const { data, error, isPending } = useQuery({
    queryKey: inventoryQueryKey,
    queryFn: readInventory,
  })

  const balances = data?.balances.data ?? []
  const movements = data?.movements.data ?? []
  const productNames = useMemo(
    () =>
      new Map(
        balances.map((balance) => [balance.product_id, balance.product_name]),
      ),
    [balances],
  )

  const trackedCount = balances.filter(
    (balance) => balance.track_inventory,
  ).length
  const lowStockCount = balances.filter(
    (balance) => balance.is_low_stock,
  ).length
  const outOfStockCount = balances.filter(
    (balance) =>
      balance.is_active &&
      balance.track_inventory &&
      Number(balance.quantity_on_hand) <= 0,
  ).length

  const filteredBalances = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    return balances.filter((balance) => {
      const matchesSearch =
        !query || balance.product_name.toLocaleLowerCase().includes(query)
      const matchesFilter =
        balanceFilter === "all" ||
        (balanceFilter === "low" && balance.is_low_stock) ||
        (balanceFilter === "out" &&
          balance.is_active &&
          balance.track_inventory &&
          Number(balance.quantity_on_hand) <= 0) ||
        (balanceFilter === "untracked" && !balance.track_inventory)
      return matchesSearch && matchesFilter
    })
  }, [balanceFilter, balances, search])

  const filteredMovements = movementFilter
    ? movements.filter((movement) => movement.product_id === movementFilter)
    : movements

  const openMovement = (productId = "") => {
    setInitialProductId(productId)
    setEditorOpen(true)
  }

  return (
    <div className="space-y-6" data-testid="inventory-page">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-primary">
            <Boxes className="size-4" />
            Stock control
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">Inventory</h1>
          <p className="mt-1 text-muted-foreground">
            Monitor stock risk and record every manual movement.
          </p>
        </div>
        <Button onClick={() => openMovement()}>
          <ClipboardPlus />
          Record movement
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Inventory unavailable</AlertTitle>
          <AlertDescription>{getErrorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}

      {isPending ? (
        <InventorySkeleton />
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              {
                label: "All products",
                value: data?.balances.count ?? balances.length,
                icon: Boxes,
                color: "bg-primary/10 text-primary",
              },
              {
                label: "Stock tracked",
                value: trackedCount,
                icon: PackageCheck,
                color:
                  "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
              },
              {
                label: "Low stock",
                value: lowStockCount,
                icon: AlertTriangle,
                color: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
              },
              {
                label: "Out of stock",
                value: outOfStockCount,
                icon: PackageX,
                color: "bg-rose-500/10 text-rose-600 dark:text-rose-400",
              },
            ].map((metric) => (
              <Card key={metric.label} className="py-5">
                <CardContent className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">
                      {metric.label}
                    </p>
                    <p className="mt-1 text-2xl font-semibold tabular-nums">
                      {metric.value}
                    </p>
                  </div>
                  <div className={cn("rounded-xl p-3", metric.color)}>
                    <metric.icon className="size-5" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </section>

          <section className="space-y-4">
            <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
              <div className="relative w-full lg:max-w-sm">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  aria-label="Search inventory"
                  className="pl-9"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search products"
                />
              </div>
              <div className="flex flex-wrap rounded-lg border bg-muted/30 p-1">
                {(["all", "low", "out", "untracked"] as const).map((filter) => (
                  <Button
                    key={filter}
                    type="button"
                    size="sm"
                    variant={balanceFilter === filter ? "secondary" : "ghost"}
                    className="capitalize"
                    onClick={() => setBalanceFilter(filter)}
                  >
                    {filter === "out" ? "Out of stock" : filter}
                  </Button>
                ))}
              </div>
            </div>

            {filteredBalances.length === 0 ? (
              <Card>
                <CardContent className="flex min-h-64 flex-col items-center justify-center text-center">
                  <div className="mb-4 rounded-full bg-muted p-4">
                    <Boxes className="size-8 text-muted-foreground" />
                  </div>
                  <h2 className="text-lg font-semibold">
                    No inventory matches
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Add or update products, or change the current filters.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Product</TableHead>
                    <TableHead>On hand</TableHead>
                    <TableHead>Reorder level</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredBalances.map((balance) => {
                    const quantity = Number(balance.quantity_on_hand)
                    const outOfStock =
                      balance.is_active &&
                      balance.track_inventory &&
                      quantity <= 0
                    return (
                      <TableRow key={balance.product_id}>
                        <TableCell>
                          <div>
                            <p className="font-medium">
                              {balance.product_name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {balance.is_active ? "Active" : "Inactive"} ·{" "}
                              {balance.unit}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span
                            className={cn(
                              "font-semibold tabular-nums",
                              outOfStock && "text-destructive",
                              balance.is_low_stock &&
                                !outOfStock &&
                                "text-amber-600 dark:text-amber-400",
                            )}
                          >
                            {quantityFormatter.format(quantity)} {balance.unit}
                          </span>
                        </TableCell>
                        <TableCell>
                          {balance.track_inventory
                            ? `${quantityFormatter.format(
                                Number(balance.reorder_level),
                              )} ${balance.unit}`
                            : "—"}
                        </TableCell>
                        <TableCell>
                          {!balance.track_inventory ? (
                            <Badge variant="outline">Not tracked</Badge>
                          ) : outOfStock ? (
                            <Badge variant="destructive">Out of stock</Badge>
                          ) : balance.is_low_stock ? (
                            <Badge variant="outline">Low stock</Badge>
                          ) : (
                            <Badge variant="secondary">Healthy</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={!balance.track_inventory}
                            onClick={() => openMovement(balance.product_id)}
                          >
                            <ClipboardPlus />
                            Record
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </section>

          <Card>
            <CardHeader className="border-b">
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-sky-500/10 p-2 text-sky-600 dark:text-sky-400">
                    <History className="size-5" />
                  </div>
                  <div>
                    <CardTitle>Movement history</CardTitle>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Latest receipts, adjustments, and sales
                    </p>
                  </div>
                </div>
                <select
                  aria-label="Filter movements by product"
                  className="border-input bg-background focus-visible:border-ring focus-visible:ring-ring/50 h-9 rounded-md border px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
                  value={movementFilter}
                  onChange={(event) => setMovementFilter(event.target.value)}
                >
                  <option value="">All products</option>
                  {balances.map((balance) => (
                    <option key={balance.product_id} value={balance.product_id}>
                      {balance.product_name}
                    </option>
                  ))}
                </select>
              </div>
            </CardHeader>
            <CardContent>
              {filteredMovements.length === 0 ? (
                <div className="flex min-h-48 flex-col items-center justify-center text-center">
                  <History className="mb-3 size-8 text-muted-foreground" />
                  <p className="font-medium">No movements recorded</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Stock activity will appear here in newest-first order.
                  </p>
                </div>
              ) : (
                <div className="divide-y">
                  {filteredMovements.slice(0, 20).map((movement) => {
                    const Icon = movementIcon(movement.movement_type)
                    const quantity = Number(movement.quantity_delta)
                    return (
                      <div
                        key={movement.id}
                        className="flex flex-col justify-between gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center"
                      >
                        <div className="flex min-w-0 items-start gap-3">
                          <div className="rounded-lg bg-muted p-2">
                            <Icon className="size-4 text-muted-foreground" />
                          </div>
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-medium">
                                {productNames.get(movement.product_id) ??
                                  "Unknown product"}
                              </p>
                              <Badge variant="outline">
                                {movementLabel(movement.movement_type)}
                              </Badge>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {new Intl.DateTimeFormat("en-AU", {
                                dateStyle: "medium",
                                timeStyle: "short",
                              }).format(new Date(movement.occurred_at))}
                              {movement.note ? ` · ${movement.note}` : ""}
                            </p>
                          </div>
                        </div>
                        <p
                          className={cn(
                            "font-semibold tabular-nums",
                            quantity > 0
                              ? "text-emerald-600 dark:text-emerald-400"
                              : "text-rose-600 dark:text-rose-400",
                          )}
                        >
                          {quantity > 0 ? "+" : ""}
                          {quantityFormatter.format(quantity)}
                        </p>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <MovementEditor
        open={editorOpen}
        balances={balances}
        initialProductId={initialProductId}
        onOpenChange={setEditorOpen}
      />
    </div>
  )
}
