import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import {
  AlertCircle,
  Bot,
  CalendarClock,
  CircleCheck,
  Clock3,
  LoaderCircle,
  Play,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { type AIDailyAutomationUpdate, AiService } from "@/client"
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
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"

const automationQueryKey = ["ai-automation", "daily-briefing"] as const

function getErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)
      ?.detail
    if (typeof detail === "string") return detail
  }
  return "The automation request could not be completed. Check the backend and try again."
}

function formatDateTime(
  value: string | null | undefined,
  timezone: string,
): string {
  if (!value) return "Not yet"
  return new Intl.DateTimeFormat("en-AU", {
    timeZone: timezone,
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function statusBadge(status: "running" | "succeeded" | "failed") {
  if (status === "succeeded") {
    return (
      <Badge
        className="border-emerald-500/40 text-emerald-700 dark:text-emerald-300"
        variant="outline"
      >
        <CircleCheck />
        Succeeded
      </Badge>
    )
  }
  if (status === "failed") {
    return (
      <Badge
        className="border-rose-500/40 text-rose-700 dark:text-rose-300"
        variant="outline"
      >
        <AlertCircle />
        Failed
      </Badge>
    )
  }
  return (
    <Badge variant="secondary">
      <LoaderCircle className="animate-spin" />
      Running
    </Badge>
  )
}

export const Route = createFileRoute("/_layout/automation")({
  component: Automation,
  head: () => ({
    meta: [{ title: "AI Automation | OpsPilot" }],
  }),
})

function Automation() {
  const queryClient = useQueryClient()
  const [enabled, setEnabled] = useState(false)
  const [runTime, setRunTime] = useState("08:00")

  const automationQuery = useQuery({
    queryKey: automationQueryKey,
    queryFn: async () => {
      const response = await AiService.readDailyBriefingAutomation()
      return response.data
    },
    refetchInterval: 30_000,
  })

  useEffect(() => {
    if (automationQuery.data) {
      setEnabled(automationQuery.data.enabled)
      setRunTime(automationQuery.data.run_time.slice(0, 5))
    }
  }, [automationQuery.data])

  const updateMutation = useMutation({
    mutationFn: async (payload: AIDailyAutomationUpdate) => {
      const response = await AiService.updateDailyBriefingAutomation({
        body: payload,
      })
      return response.data
    },
    onSuccess: (automation) => {
      queryClient.setQueryData(automationQueryKey, automation)
      toast.success(
        automation.enabled
          ? "Daily briefing automation enabled"
          : "Daily briefing automation paused",
      )
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const runMutation = useMutation({
    mutationFn: async () => {
      const response = await AiService.runDailyBriefingAutomation()
      return response.data
    },
    onSuccess: async (run) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: automationQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["ai-daily-briefing"] }),
      ])
      if (run.status === "failed") {
        toast.error("Automation run failed", {
          description: run.error ?? "Local AI could not create the briefing.",
        })
        return
      }
      toast.success("Daily briefing generated automatically")
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const automation = automationQuery.data
  const hasChanges = Boolean(
    automation &&
      (enabled !== automation.enabled ||
        runTime !== automation.run_time.slice(0, 5)),
  )

  if (automationQuery.isPending) {
    return (
      <div
        className="space-y-6"
        role="status"
        aria-label="Loading AI automation"
      >
        <Skeleton className="h-48 rounded-2xl" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-80 rounded-xl" />
          <Skeleton className="h-80 rounded-xl" />
        </div>
      </div>
    )
  }

  if (automationQuery.error || !automation) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertTitle>AI automation unavailable</AlertTitle>
        <AlertDescription>
          {getErrorMessage(automationQuery.error)}
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6" data-testid="ai-automation">
      <section className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-violet-500/15 via-background to-background p-6 shadow-sm md:p-8">
        <div className="absolute -right-20 -top-24 size-72 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="relative flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div className="max-w-2xl">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-violet-700 dark:text-violet-300">
              <Bot className="size-4" />
              Approval-first automation
            </div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Daily AI automation
            </h1>
            <p className="mt-3 text-muted-foreground">
              Let OpsPilot prepare a grounded daily briefing on schedule while
              keeping operational changes under your control.
            </p>
          </div>
          <Badge variant={automation.enabled ? "default" : "secondary"}>
            {automation.enabled ? "Schedule active" : "Schedule paused"}
          </Badge>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="py-5">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <CalendarClock className="size-4" />
              Next scheduled run
            </div>
            <p className="mt-2 font-semibold">
              {automation.enabled
                ? formatDateTime(automation.next_run_at, automation.timezone)
                : "Paused"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-5">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Clock3 className="size-4" />
              Business timezone
            </div>
            <p className="mt-2 font-semibold">{automation.timezone}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-5">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Sparkles className="size-4" />
              Last run
            </div>
            <div className="mt-2">
              {automation.last_run
                ? statusBadge(automation.last_run.status)
                : "No runs yet"}
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader className="border-b">
            <CardTitle>Daily briefing schedule</CardTitle>
            <CardDescription>
              The worker creates at most one scheduled briefing per business
              day.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 py-6">
            <div className="flex items-start gap-3 rounded-xl border p-4">
              <Checkbox
                id="daily-automation-enabled"
                checked={enabled}
                onCheckedChange={(checked) => setEnabled(checked === true)}
              />
              <div className="grid gap-1.5">
                <Label htmlFor="daily-automation-enabled">
                  Generate my daily briefing automatically
                </Label>
                <p className="text-sm text-muted-foreground">
                  OpsPilot reads the daily dashboard snapshot and saves the AI
                  result to briefing history.
                </p>
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="daily-automation-time">Run time</Label>
              <Input
                className="max-w-48"
                id="daily-automation-time"
                type="time"
                value={runTime}
                onChange={(event) => setRunTime(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Uses {automation.timezone}. The automation service must be
                running at this time.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                disabled={!hasChanges || updateMutation.isPending || !runTime}
                onClick={() =>
                  updateMutation.mutate({
                    enabled,
                    run_time: `${runTime}:00`,
                  })
                }
              >
                {updateMutation.isPending ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <CalendarClock />
                )}
                Save schedule
              </Button>
              <Button
                variant="outline"
                disabled={runMutation.isPending}
                onClick={() => runMutation.mutate()}
              >
                {runMutation.isPending ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <Play />
                )}
                {runMutation.isPending ? "Running..." : "Run now"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Latest automation run</CardTitle>
              <CardDescription>
                Every attempt is recorded for auditability.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {automation.last_run ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {statusBadge(automation.last_run.status)}
                    <Badge variant="secondary">
                      {automation.last_run.trigger === "scheduled"
                        ? "Scheduled"
                        : "Run now"}
                    </Badge>
                  </div>
                  <dl className="grid gap-3 text-sm">
                    <div>
                      <dt className="text-muted-foreground">Started</dt>
                      <dd className="font-medium">
                        {formatDateTime(
                          automation.last_run.started_at,
                          automation.timezone,
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Completed</dt>
                      <dd className="font-medium">
                        {formatDateTime(
                          automation.last_run.completed_at,
                          automation.timezone,
                        )}
                      </dd>
                    </div>
                  </dl>
                  {automation.last_run.error ? (
                    <Alert variant="destructive">
                      <AlertCircle />
                      <AlertTitle>Run failed</AlertTitle>
                      <AlertDescription>
                        {automation.last_run.error}
                      </AlertDescription>
                    </Alert>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Save a schedule or choose Run now to create the first audit
                  record.
                </p>
              )}
            </CardContent>
          </Card>

          <Card className="border-emerald-500/25 bg-emerald-500/5">
            <CardHeader>
              <div className="flex items-center gap-2">
                <ShieldCheck className="size-5 text-emerald-600" />
                <CardTitle>Automation guardrails</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>Reads only the deterministic daily operations snapshot.</li>
                <li>Creates a saved briefing with its source data attached.</li>
                <li>Never changes products, inventory, sales, or actions.</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  )
}
