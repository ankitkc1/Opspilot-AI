import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import {
  AlertCircle,
  CalendarDays,
  CircleCheck,
  Clock3,
  ListChecks,
  LoaderCircle,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import {
  type ActionItemCreate,
  type ActionItemPublic,
  type ActionItemUpdate,
  ActionsService,
  type AIDailyBriefingPublic,
} from "@/client"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

type ActionStatus = ActionItemPublic["status"]
type ActionCategory = NonNullable<ActionItemPublic["category"]>
type ActionPriority = NonNullable<ActionItemPublic["priority"]>
type StatusFilter = "all" | ActionStatus
type CategoryFilter = "all" | ActionCategory

type ActionForm = {
  title: string
  description: string
  category: ActionCategory
  priority: ActionPriority
  due_date: string
}

const actionsQueryKey = ["actions"] as const

const emptyAction: ActionForm = {
  title: "",
  description: "",
  category: "priority",
  priority: "medium",
  due_date: "",
}

const statusLabels: Record<ActionStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  completed: "Completed",
  dismissed: "Dismissed",
}

const categoryLabels: Record<ActionCategory, string> = {
  priority: "Priority",
  risk: "Risk",
  opportunity: "Opportunity",
}

const priorityLabels: Record<ActionPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
}

function localDateString(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset()
  return new Date(now.getTime() - offset * 60_000).toISOString().slice(0, 10)
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "No due date"
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium" }).format(
    new Date(`${value}T00:00:00`),
  )
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function actionToForm(action?: ActionItemPublic | null): ActionForm {
  if (!action) return emptyAction
  return {
    title: action.title,
    description: action.description ?? "",
    category: action.category,
    priority: action.priority,
    due_date: action.due_date ?? "",
  }
}

function getErrorMessage(error: unknown): string {
  if (!isAxiosError(error)) {
    return "The request could not be completed. Please try again."
  }
  const detail = (error.response?.data as { detail?: unknown } | undefined)
    ?.detail
  return typeof detail === "string"
    ? detail
    : "The request could not be completed. Please try again."
}

function statusBadgeClass(status: ActionStatus): string {
  if (status === "completed") {
    return "border-emerald-500/40 text-emerald-700 dark:text-emerald-300"
  }
  if (status === "in_progress") {
    return "border-sky-500/40 text-sky-700 dark:text-sky-300"
  }
  if (status === "dismissed") {
    return "text-muted-foreground"
  }
  return "border-amber-500/40 text-amber-700 dark:text-amber-300"
}

function categoryBadgeClass(category: ActionCategory): string {
  if (category === "risk") {
    return "border-rose-500/40 text-rose-700 dark:text-rose-300"
  }
  if (category === "opportunity") {
    return "border-violet-500/40 text-violet-700 dark:text-violet-300"
  }
  return "border-sky-500/40 text-sky-700 dark:text-sky-300"
}

function priorityBadgeClass(priority: ActionPriority): string {
  if (priority === "high") return "bg-rose-500/10 text-rose-700"
  if (priority === "low") return "bg-muted text-muted-foreground"
  return "bg-amber-500/10 text-amber-700"
}

export const Route = createFileRoute("/_layout/actions")({
  component: Actions,
  head: () => ({
    meta: [{ title: "Action Center | OpsPilot" }],
  }),
})

function ActionEditor({
  action,
  open,
  onOpenChange,
}: {
  action?: ActionItemPublic | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<ActionForm>(() => actionToForm(action))
  const [formError, setFormError] = useState<string | null>(null)
  const isEditing = Boolean(action)

  useEffect(() => {
    if (open) {
      setForm(actionToForm(action))
      setFormError(null)
    }
  }, [action, open])

  const saveMutation = useMutation({
    mutationFn: async (payload: ActionItemCreate | ActionItemUpdate) => {
      const response = action
        ? await ActionsService.updateAction({
            path: { action_id: action.id },
            body: payload,
          })
        : await ActionsService.createAction({
            body: payload as ActionItemCreate,
          })
      return response.data
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: actionsQueryKey })
      toast.success(isEditing ? "Action updated" : "Action created")
      setForm(emptyAction)
      setFormError(null)
      onOpenChange(false)
    },
  })

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const title = form.title.trim()
    if (!title) {
      setFormError("Title is required.")
      return
    }
    setFormError(null)
    saveMutation.mutate({
      title,
      description: form.description.trim() || null,
      category: form.category,
      priority: form.priority,
      due_date: form.due_date || null,
    })
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!saveMutation.isPending) {
          onOpenChange(nextOpen)
          if (!nextOpen) {
            setForm(emptyAction)
            setFormError(null)
            saveMutation.reset()
          }
        }
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>
              {isEditing ? "Edit action" : "Create action"}
            </DialogTitle>
            <DialogDescription>
              {isEditing
                ? "Update the task details while keeping its original source."
                : "Add an operational task for you to review and complete."}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-5">
            <div className="grid gap-2">
              <Label htmlFor="action-title">Title</Label>
              <Input
                id="action-title"
                maxLength={255}
                value={form.title}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    title: event.target.value,
                  }))
                }
                placeholder="Confirm tomorrow's stock order"
                autoFocus
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="action-description">Notes</Label>
              <Input
                id="action-description"
                maxLength={1000}
                value={form.description}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    description: event.target.value,
                  }))
                }
                placeholder="Optional context for this action"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>Category</Label>
                <Select
                  value={form.category}
                  onValueChange={(value: ActionCategory) =>
                    setForm((current) => ({ ...current, category: value }))
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="priority">Priority</SelectItem>
                    <SelectItem value="risk">Risk</SelectItem>
                    <SelectItem value="opportunity">Opportunity</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label>Priority</Label>
                <Select
                  value={form.priority}
                  onValueChange={(value: ActionPriority) =>
                    setForm((current) => ({ ...current, priority: value }))
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="action-due-date">Due date</Label>
              <Input
                id="action-due-date"
                type="date"
                value={form.due_date}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    due_date: event.target.value,
                  }))
                }
              />
            </div>

            {formError || saveMutation.error ? (
              <Alert variant="destructive">
                <AlertCircle />
                <AlertTitle>
                  Action not {isEditing ? "updated" : "created"}
                </AlertTitle>
                <AlertDescription>
                  {formError ?? getErrorMessage(saveMutation.error)}
                </AlertDescription>
              </Alert>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saveMutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? (
                <LoaderCircle className="animate-spin" />
              ) : isEditing ? (
                <Pencil />
              ) : (
                <Plus />
              )}
              {isEditing ? "Save changes" : "Create action"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function SourceBriefingDialog({
  action,
  onOpenChange,
}: {
  action: ActionItemPublic | null
  onOpenChange: (open: boolean) => void
}) {
  const sourceQuery = useQuery<AIDailyBriefingPublic>({
    queryKey: ["actions", "source-briefing", action?.id],
    queryFn: async () => {
      if (!action) throw new Error("No action selected")
      const response = await ActionsService.readActionSourceBriefing({
        path: { action_id: action.id },
      })
      return response.data
    },
    enabled: Boolean(action),
  })
  const sourceSuggestion = action?.source_suggestion ?? action?.title
  const sourceCategory = sourceQuery.data
    ? sourceQuery.data.priorities.includes(sourceSuggestion ?? "")
      ? "priority"
      : sourceQuery.data.risks.includes(sourceSuggestion ?? "")
        ? "risk"
        : sourceQuery.data.opportunities.includes(sourceSuggestion ?? "")
          ? "opportunity"
          : action?.category
    : action?.category

  return (
    <Dialog open={Boolean(action)} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Source briefing</DialogTitle>
          <DialogDescription>
            The saved AI briefing that produced this approved action.
          </DialogDescription>
        </DialogHeader>

        {sourceQuery.error ? (
          <Alert variant="destructive">
            <AlertCircle />
            <AlertTitle>Source unavailable</AlertTitle>
            <AlertDescription>
              {getErrorMessage(sourceQuery.error)}
            </AlertDescription>
          </Alert>
        ) : sourceQuery.isPending || !sourceQuery.data ? (
          <div className="space-y-3 py-4" role="status">
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : (
          <div className="space-y-5 py-2">
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">
                {formatDate(sourceQuery.data.report_date)}
              </Badge>
              <Badge variant="outline">{sourceQuery.data.model}</Badge>
            </div>
            <div>
              <h3 className="font-semibold">{sourceQuery.data.headline}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {sourceQuery.data.summary}
              </p>
            </div>
            <div className="rounded-lg border bg-muted/40 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Original {sourceCategory ?? "priority"} suggestion
              </p>
              <p className="mt-2 text-sm font-medium">{sourceSuggestion}</p>
            </div>
            <p className="text-xs text-muted-foreground">
              Generated {formatDateTime(sourceQuery.data.generated_at)}
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function SummaryCard({
  label,
  value,
  icon: Icon,
  iconClassName,
}: {
  label: string
  value: number
  icon: typeof ListChecks
  iconClassName: string
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between py-5">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-3xl font-semibold tabular-nums">{value}</p>
        </div>
        <div className={cn("rounded-xl p-3", iconClassName)}>
          <Icon className="size-5" />
        </div>
      </CardContent>
    </Card>
  )
}

function Actions() {
  const queryClient = useQueryClient()
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingAction, setEditingAction] = useState<ActionItemPublic | null>(
    null,
  )
  const [sourceAction, setSourceAction] = useState<ActionItemPublic | null>(
    null,
  )
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all")

  const actionsQuery = useQuery({
    queryKey: actionsQueryKey,
    queryFn: async () => {
      const response = await ActionsService.readActions({
        query: { skip: 0, limit: 100 },
      })
      return response.data
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({
      actionId,
      payload,
    }: {
      actionId: string
      payload: ActionItemUpdate
    }) => {
      const response = await ActionsService.updateAction({
        path: { action_id: actionId },
        body: payload,
      })
      return response.data
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: actionsQueryKey })
      toast.success("Action updated")
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const deleteMutation = useMutation({
    mutationFn: async (actionId: string) => {
      await ActionsService.deleteAction({ path: { action_id: actionId } })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: actionsQueryKey })
      toast.success("Action deleted")
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const actions = actionsQuery.data?.data ?? []
  const today = localDateString()
  const filteredActions = useMemo(
    () =>
      actions.filter(
        (action) =>
          (statusFilter === "all" || action.status === statusFilter) &&
          (categoryFilter === "all" || action.category === categoryFilter),
      ),
    [actions, categoryFilter, statusFilter],
  )
  const activeCount = actions.filter(
    (action) => action.status === "open" || action.status === "in_progress",
  ).length
  const inProgressCount = actions.filter(
    (action) => action.status === "in_progress",
  ).length
  const completedCount = actions.filter(
    (action) => action.status === "completed",
  ).length
  const overdueCount = actions.filter(
    (action) =>
      Boolean(action.due_date) &&
      action.due_date! < today &&
      action.status !== "completed" &&
      action.status !== "dismissed",
  ).length

  return (
    <div className="space-y-6" data-testid="action-center">
      <section className="flex flex-col justify-between gap-4 rounded-2xl border bg-gradient-to-br from-primary/15 via-background to-background p-6 shadow-sm md:flex-row md:items-end md:p-8">
        <div className="max-w-2xl">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-primary">
            <ListChecks className="size-4" />
            OpsPilot action center
          </div>
          <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Turn insight into action
          </h1>
          <p className="mt-3 text-muted-foreground">
            Review AI suggestions, assign priorities, and track the work you
            choose to approve.
          </p>
        </div>
        <Button
          onClick={() => {
            setEditingAction(null)
            setEditorOpen(true)
          }}
        >
          <Plus />
          New action
        </Button>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          label="Active"
          value={activeCount}
          icon={ListChecks}
          iconClassName="bg-sky-500/10 text-sky-600"
        />
        <SummaryCard
          label="In progress"
          value={inProgressCount}
          icon={Clock3}
          iconClassName="bg-violet-500/10 text-violet-600"
        />
        <SummaryCard
          label="Completed"
          value={completedCount}
          icon={CircleCheck}
          iconClassName="bg-emerald-500/10 text-emerald-600"
        />
        <SummaryCard
          label="Overdue"
          value={overdueCount}
          icon={AlertCircle}
          iconClassName="bg-rose-500/10 text-rose-600"
        />
      </section>

      <Card>
        <CardHeader className="border-b">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div>
              <CardTitle>Actions</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                {filteredActions.length} of {actions.length} actions shown
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Select
                value={statusFilter}
                onValueChange={(value: StatusFilter) => setStatusFilter(value)}
              >
                <SelectTrigger className="w-full sm:w-40">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="in_progress">In progress</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="dismissed">Dismissed</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={categoryFilter}
                onValueChange={(value: CategoryFilter) =>
                  setCategoryFilter(value)
                }
              >
                <SelectTrigger className="w-full sm:w-40">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All categories</SelectItem>
                  <SelectItem value="priority">Priorities</SelectItem>
                  <SelectItem value="risk">Risks</SelectItem>
                  <SelectItem value="opportunity">Opportunities</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>

        <CardContent className="py-6">
          {actionsQuery.error ? (
            <Alert variant="destructive">
              <AlertCircle />
              <AlertTitle>Actions unavailable</AlertTitle>
              <AlertDescription>
                {getErrorMessage(actionsQuery.error)}
              </AlertDescription>
            </Alert>
          ) : actionsQuery.isPending ? (
            <div
              className="space-y-3"
              aria-label="Loading actions"
              role="status"
            >
              {Array.from({ length: 3 }, (_, index) => (
                <Skeleton className="h-36 rounded-xl" key={index} />
              ))}
            </div>
          ) : filteredActions.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center text-center">
              <div className="mb-4 rounded-full bg-violet-500/10 p-4">
                <Sparkles className="size-7 text-violet-600" />
              </div>
              <p className="font-medium">No matching actions</p>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Create an action here or approve a suggestion from the daily AI
                briefing.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              {filteredActions.map((action) => {
                const category = action.category ?? "priority"
                const priority = action.priority ?? "medium"
                const isOverdue =
                  Boolean(action.due_date) &&
                  action.due_date! < today &&
                  action.status !== "completed" &&
                  action.status !== "dismissed"

                return (
                  <div
                    className="rounded-xl border bg-background/70 p-5"
                    key={action.id}
                  >
                    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                      <div className="min-w-0">
                        <div className="mb-3 flex flex-wrap gap-2">
                          <Badge
                            variant="outline"
                            className={categoryBadgeClass(category)}
                          >
                            {categoryLabels[category]}
                          </Badge>
                          <Badge className={priorityBadgeClass(priority)}>
                            {priorityLabels[priority]} priority
                          </Badge>
                          <Badge
                            variant="outline"
                            className={statusBadgeClass(action.status)}
                          >
                            {statusLabels[action.status]}
                          </Badge>
                        </div>
                        <h2 className="font-semibold leading-6">
                          {action.title}
                        </h2>
                        {action.description ? (
                          <p className="mt-2 text-sm leading-6 text-muted-foreground">
                            {action.description}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 gap-1">
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={`Edit ${action.title}`}
                          onClick={() => {
                            setEditingAction(action)
                            setEditorOpen(true)
                          }}
                        >
                          <Pencil />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={`Delete ${action.title}`}
                          disabled={deleteMutation.isPending}
                          onClick={() => {
                            if (
                              window.confirm(
                                `Delete the action “${action.title}”?`,
                              )
                            ) {
                              deleteMutation.mutate(action.id)
                            }
                          }}
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </div>

                    <div className="mt-5 flex flex-col justify-between gap-3 border-t pt-4 sm:flex-row sm:items-center">
                      <div className="flex flex-wrap items-center gap-2">
                        <div
                          className={cn(
                            "flex items-center gap-2 text-xs text-muted-foreground",
                            isOverdue && "font-medium text-destructive",
                          )}
                        >
                          <CalendarDays className="size-4" />
                          {isOverdue ? "Overdue · " : ""}
                          {formatDate(action.due_date)}
                        </div>
                        {action.source_briefing_id ? (
                          <Button
                            className="h-auto px-1 py-0 text-xs"
                            size="sm"
                            variant="link"
                            onClick={() => setSourceAction(action)}
                          >
                            <Sparkles />
                            View source
                          </Button>
                        ) : null}
                      </div>
                      <Select
                        value={action.status}
                        disabled={updateMutation.isPending}
                        onValueChange={(value: ActionStatus) =>
                          updateMutation.mutate({
                            actionId: action.id,
                            payload: { status: value },
                          })
                        }
                      >
                        <SelectTrigger className="w-full sm:w-40" size="sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="open">Open</SelectItem>
                          <SelectItem value="in_progress">
                            In progress
                          </SelectItem>
                          <SelectItem value="completed">Completed</SelectItem>
                          <SelectItem value="dismissed">Dismissed</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <ActionEditor
        action={editingAction}
        open={editorOpen}
        onOpenChange={(nextOpen) => {
          setEditorOpen(nextOpen)
          if (!nextOpen) setEditingAction(null)
        }}
      />
      <SourceBriefingDialog
        action={sourceAction}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setSourceAction(null)
        }}
      />
    </div>
  )
}
