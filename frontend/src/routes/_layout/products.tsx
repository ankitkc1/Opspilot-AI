import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import {
  Boxes,
  CircleDollarSign,
  Edit3,
  LoaderCircle,
  PackageOpen,
  Plus,
  Power,
  Search,
  Tags,
} from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { client } from "@/client/client.gen"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
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
  reorder_level: string | number
  created_at: string
}

type ProductsResponse = {
  data: Product[]
  count: number
}

type ProductPayload = {
  name: string
  category: string
  selling_price: string
  unit: string
  is_active: boolean
  track_inventory: boolean
  reorder_level: string
}

type ProductFormState = ProductPayload
type StatusFilter = "all" | "active" | "inactive"

const emptyProduct: ProductFormState = {
  name: "",
  category: "",
  selling_price: "",
  unit: "each",
  is_active: true,
  track_inventory: false,
  reorder_level: "0",
}

const currencyFormatter = new Intl.NumberFormat("en-AU", {
  style: "currency",
  currency: "AUD",
})

const productQueryKey = ["products"] as const

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

async function createProduct(payload: ProductPayload): Promise<Product> {
  const response = await client.post<{ 201: Product }, never, true>({
    url: "/api/v1/products/",
    body: payload,
    security: [{ scheme: "bearer", type: "http" }],
    responseType: "json",
    throwOnError: true,
  })
  return response.data
}

async function updateProduct(
  productId: string,
  payload: Partial<ProductPayload>,
): Promise<Product> {
  const response = await client.patch<{ 200: Product }, never, true>({
    url: `/api/v1/products/${productId}`,
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

function productToForm(product: Product | null): ProductFormState {
  if (!product) {
    return { ...emptyProduct }
  }
  return {
    name: product.name,
    category: product.category,
    selling_price: String(product.selling_price),
    unit: product.unit,
    is_active: product.is_active,
    track_inventory: product.track_inventory,
    reorder_level: String(product.reorder_level),
  }
}

function validateProduct(form: ProductFormState): string | null {
  if (!form.name.trim() || !form.category.trim() || !form.unit.trim()) {
    return "Name, category, and unit are required."
  }

  const price = Number(form.selling_price)
  if (!Number.isFinite(price) || price < 0) {
    return "Selling price must be zero or greater."
  }

  const reorderLevel = Number(form.reorder_level)
  if (!Number.isFinite(reorderLevel) || reorderLevel < 0) {
    return "Reorder level must be zero or greater."
  }

  return null
}

export const Route = createFileRoute("/_layout/products")({
  component: Products,
  head: () => ({
    meta: [{ title: "Products | OpsPilot" }],
  }),
})

type ProductEditorProps = {
  open: boolean
  product: Product | null
  onOpenChange: (open: boolean) => void
}

function ProductEditor({ open, product, onOpenChange }: ProductEditorProps) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<ProductFormState>(() =>
    productToForm(product),
  )
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setForm(productToForm(product))
      setFormError(null)
    }
  }, [open, product])

  const mutation = useMutation({
    mutationFn: (payload: ProductPayload) =>
      product ? updateProduct(product.id, payload) : createProduct(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: productQueryKey })
      toast.success(product ? "Product updated" : "Product created", {
        description: `${form.name.trim()} is ready in your catalogue.`,
      })
      onOpenChange(false)
    },
    onError: (error) => setFormError(getErrorMessage(error)),
  })

  const setField = <Key extends keyof ProductFormState>(
    key: Key,
    value: ProductFormState[Key],
  ) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validationError = validateProduct(form)
    if (validationError) {
      setFormError(validationError)
      return
    }

    setFormError(null)
    mutation.mutate({
      ...form,
      name: form.name.trim(),
      category: form.category.trim(),
      unit: form.unit.trim(),
      selling_price: Number(form.selling_price).toFixed(2),
      reorder_level: form.track_inventory
        ? Number(form.reorder_level).toFixed(3)
        : "0.000",
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <form onSubmit={handleSubmit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>
              {product ? "Edit product" : "Add product"}
            </DialogTitle>
            <DialogDescription>
              Set the product details used by sales, inventory, and reporting.
            </DialogDescription>
          </DialogHeader>

          {formError ? (
            <Alert variant="destructive">
              <AlertTitle>Check the product details</AlertTitle>
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="product-name">Product name</Label>
              <Input
                id="product-name"
                value={form.name}
                onChange={(event) => setField("name", event.target.value)}
                placeholder="Flat White"
                maxLength={255}
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="product-category">Category</Label>
              <Input
                id="product-category"
                value={form.category}
                onChange={(event) => setField("category", event.target.value)}
                placeholder="Coffee"
                maxLength={100}
                list="product-categories"
              />
              <datalist id="product-categories">
                <option value="Coffee" />
                <option value="Food" />
                <option value="Beverage" />
                <option value="Retail" />
              </datalist>
            </div>
            <div className="space-y-2">
              <Label htmlFor="product-unit">Unit</Label>
              <Input
                id="product-unit"
                value={form.unit}
                onChange={(event) => setField("unit", event.target.value)}
                placeholder="each"
                maxLength={50}
                list="product-units"
              />
              <datalist id="product-units">
                <option value="each" />
                <option value="kg" />
                <option value="litre" />
                <option value="serve" />
              </datalist>
            </div>
            <div className="space-y-2">
              <Label htmlFor="product-price">Selling price (AUD)</Label>
              <Input
                id="product-price"
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={form.selling_price}
                onChange={(event) =>
                  setField("selling_price", event.target.value)
                }
                placeholder="5.50"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reorder-level">Reorder level</Label>
              <Input
                id="reorder-level"
                type="number"
                min="0"
                step="0.001"
                inputMode="decimal"
                value={form.reorder_level}
                onChange={(event) =>
                  setField("reorder_level", event.target.value)
                }
                disabled={!form.track_inventory}
              />
            </div>
          </div>

          <div className="space-y-3 rounded-lg border bg-muted/30 p-4">
            <div className="flex items-start gap-3">
              <Checkbox
                id="track-inventory"
                checked={form.track_inventory}
                onCheckedChange={(checked) =>
                  setField("track_inventory", checked === true)
                }
              />
              <div className="grid gap-1">
                <Label htmlFor="track-inventory">Track inventory</Label>
                <p className="text-xs text-muted-foreground">
                  Include this product in stock balances and low-stock alerts.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Checkbox
                id="product-active"
                checked={form.is_active}
                onCheckedChange={(checked) =>
                  setField("is_active", checked === true)
                }
              />
              <div className="grid gap-1">
                <Label htmlFor="product-active">Active product</Label>
                <p className="text-xs text-muted-foreground">
                  Active products can be selected when recording sales.
                </p>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <LoaderCircle className="animate-spin" />
              ) : null}
              {product ? "Save changes" : "Create product"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ProductsSkeleton() {
  return (
    <div className="space-y-4" aria-label="Loading products" role="status">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-80 rounded-xl" />
    </div>
  )
}

function Products() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)

  const { data, error, isPending } = useQuery({
    queryKey: productQueryKey,
    queryFn: readProducts,
  })

  const statusMutation = useMutation({
    mutationFn: ({
      product,
      isActive,
    }: {
      product: Product
      isActive: boolean
    }) => updateProduct(product.id, { is_active: isActive }),
    onSuccess: async (updatedProduct) => {
      await queryClient.invalidateQueries({ queryKey: productQueryKey })
      toast.success(
        updatedProduct.is_active ? "Product activated" : "Product deactivated",
        { description: updatedProduct.name },
      )
    },
    onError: (mutationError) =>
      toast.error("Product status was not changed", {
        description: getErrorMessage(mutationError),
      }),
  })

  const products = data?.data ?? []
  const filteredProducts = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    return products.filter((product) => {
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" && product.is_active) ||
        (statusFilter === "inactive" && !product.is_active)
      const matchesSearch =
        !query ||
        product.name.toLocaleLowerCase().includes(query) ||
        product.category.toLocaleLowerCase().includes(query)
      return matchesStatus && matchesSearch
    })
  }, [products, search, statusFilter])

  const activeCount = products.filter((product) => product.is_active).length
  const trackedCount = products.filter(
    (product) => product.track_inventory,
  ).length
  const categoryCount = new Set(products.map((product) => product.category))
    .size

  const openCreate = () => {
    setEditingProduct(null)
    setEditorOpen(true)
  }

  const openEdit = (product: Product) => {
    setEditingProduct(product)
    setEditorOpen(true)
  }

  return (
    <div className="space-y-6" data-testid="products-page">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-primary">
            <PackageOpen className="size-4" />
            Catalogue
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">Products</h1>
          <p className="mt-1 text-muted-foreground">
            Manage what you sell and which products need stock tracking.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus />
          Add product
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Products unavailable</AlertTitle>
          <AlertDescription>{getErrorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}

      {isPending ? (
        <ProductsSkeleton />
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              {
                label: "Total products",
                value: data?.count ?? products.length,
                icon: PackageOpen,
                color: "bg-primary/10 text-primary",
              },
              {
                label: "Active",
                value: activeCount,
                icon: Power,
                color:
                  "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
              },
              {
                label: "Stock tracked",
                value: trackedCount,
                icon: Boxes,
                color: "bg-violet-500/10 text-violet-600 dark:text-violet-400",
              },
              {
                label: "Categories",
                value: categoryCount,
                icon: Tags,
                color: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
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
                  aria-label="Search products"
                  className="pl-9"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search name or category"
                />
              </div>
              <div className="flex rounded-lg border bg-muted/30 p-1">
                {(["all", "active", "inactive"] as const).map((filter) => (
                  <Button
                    key={filter}
                    type="button"
                    size="sm"
                    variant={statusFilter === filter ? "secondary" : "ghost"}
                    className="capitalize"
                    onClick={() => setStatusFilter(filter)}
                  >
                    {filter}
                  </Button>
                ))}
              </div>
            </div>

            {filteredProducts.length === 0 ? (
              <Card>
                <CardContent className="flex min-h-72 flex-col items-center justify-center text-center">
                  <div className="mb-4 rounded-full bg-muted p-4">
                    <PackageOpen className="size-8 text-muted-foreground" />
                  </div>
                  <h2 className="text-lg font-semibold">
                    {products.length === 0
                      ? "Create your first product"
                      : "No products match"}
                  </h2>
                  <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                    {products.length === 0
                      ? "Add a product to start recording stock and sales in OpsPilot."
                      : "Try changing the search text or status filter."}
                  </p>
                  {products.length === 0 ? (
                    <Button className="mt-5" onClick={openCreate}>
                      <Plus />
                      Add product
                    </Button>
                  ) : null}
                </CardContent>
              </Card>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Product</TableHead>
                    <TableHead>Price</TableHead>
                    <TableHead>Inventory</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredProducts.map((product) => {
                    const isUpdatingStatus =
                      statusMutation.isPending &&
                      statusMutation.variables?.product.id === product.id
                    return (
                      <TableRow key={product.id}>
                        <TableCell>
                          <div>
                            <p className="font-medium">{product.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {product.category} · {product.unit}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1.5 font-medium tabular-nums">
                            <CircleDollarSign className="size-4 text-muted-foreground" />
                            {currencyFormatter.format(
                              Number(product.selling_price),
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {product.track_inventory ? (
                            <div>
                              <Badge variant="outline">Tracked</Badge>
                              <p className="mt-1 text-xs text-muted-foreground">
                                Reorder at {Number(product.reorder_level)}
                              </p>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">
                              Not tracked
                            </span>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              product.is_active ? "secondary" : "outline"
                            }
                          >
                            {product.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => openEdit(product)}
                            >
                              <Edit3 />
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={isUpdatingStatus}
                              onClick={() =>
                                statusMutation.mutate({
                                  product,
                                  isActive: !product.is_active,
                                })
                              }
                            >
                              {isUpdatingStatus ? (
                                <LoaderCircle className="animate-spin" />
                              ) : (
                                <Power />
                              )}
                              {product.is_active ? "Deactivate" : "Activate"}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </section>
        </>
      )}

      <ProductEditor
        open={editorOpen}
        product={editingProduct}
        onOpenChange={setEditorOpen}
      />
    </div>
  )
}
