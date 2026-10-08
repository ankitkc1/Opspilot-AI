import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { isAxiosError } from "axios"
import {
  AlertCircle,
  Bot,
  CalendarClock,
  CalendarDays,
  CircleCheck,
  Clock3,
  LoaderCircle,
  Play,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import {
  type AIAutomationRunPublic,
  type AIDailyAutomationUpdate,
  type AIWeeklyAutomationUpdate,
  AiService,
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
import { Checkbox } from "@/components/ui/checkbox"
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

const dailyAutomationQueryKey = ["ai-automation", "daily-briefing"] as const
const weeklyAutomationQueryKey = ["ai-automation", "weekly-review"] as const

const weekdays = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const

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

function formatDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number)
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium" }).format(
    new Date(year, month - 1, day),
  )
}

function statusBadge(status: AIAutomationRunPublic["status"]) {
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

function RunSummary({
  emptyMessage,
  run,
  timezone,
}: {
  emptyMessage: string
  run: AIAutomationRunPublic | null
  timezone: string
}) {
  if (!run) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {statusBadge(run.status)}
        <Badge variant="secondary">
          {run.trigger === "scheduled" ? "Scheduled" : "Run now"}
        </Badge>
      </div>
      <dl className="grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">Scheduled for</dt>
          <dd className="font-medium">{formatDate(run.scheduled_for)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Started</dt>
          <dd className="font-medium">
            {formatDateTime(run.started_at, timezone)}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Completed</dt>
          <dd className="font-medium">
            {formatDateTime(run.completed_at, timezone)}
          </dd>
        </div>
      </dl>
      {run.error ? (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>Run failed</AlertTitle>
          <AlertDescription>{run.error}</AlertDescription>
        </Alert>
      ) : null}
    </div>
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
  const [dailyEnabled, setDailyEnabled] = useState(false)
  const [dailyRunTime, setDailyRunTime] = useState("08:00")
  const [weeklyEnabled, setWeeklyEnabled] = useState(false)
  const [weeklyWeekday, setWeeklyWeekday] = useState(0)
  const [weeklyRunTime, setWeeklyRunTime] = useState("09:00")

  const dailyQuery = useQuery({
    queryKey: dailyAutomationQueryKey,
    queryFn: async () => {
      const response = await AiService.readDailyBriefingAutomation()
      return response.data
    },
    refetchInterval: 30_000,
  })
  const weeklyQuery = useQuery({
    queryKey: weeklyAutomationQueryKey,
    queryFn: async () => {
      const response = await AiService.readWeeklyReviewAutomation()
      return response.data
    },
    refetchInterval: 30_000,
  })

  useEffect(() => {
    if (dailyQuery.data) {
      setDailyEnabled(dailyQuery.data.enabled)
      setDailyRunTime(dailyQuery.data.run_time.slice(0, 5))
    }
  }, [dailyQuery.data])

  useEffect(() => {
    if (weeklyQuery.data) {
      setWeeklyEnabled(weeklyQuery.data.enabled)
      setWeeklyWeekday(weeklyQuery.data.weekday)
      setWeeklyRunTime(weeklyQuery.data.run_time.slice(0, 5))
    }
  }, [weeklyQuery.data])

  const updateDailyMutation = useMutation({
    mutationFn: async (payload: AIDailyAutomationUpdate) => {
      const response = await AiService.updateDailyBriefingAutomation({
        body: payload,
      })
      return response.data
    },
    onSuccess: (automation) => {
      queryClient.setQueryData(dailyAutomationQueryKey, automation)
      toast.success(
        automation.enabled
          ? "Daily briefing automation enabled"
          : "Daily briefing automation paused",
      )
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const updateWeeklyMutation = useMutation({
    mutationFn: async (payload: AIWeeklyAutomationUpdate) => {
      const response = await AiService.updateWeeklyReviewAutomation({
        body: payload,
      })
      return response.data
    },
    onSuccess: (automation) => {
      queryClient.setQueryData(weeklyAutomationQueryKey, automation)
      toast.success(
        automation.enabled
          ? "Weekly review automation enabled"
          : "Weekly review automation paused",
      )
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const runDailyMutation = useMutation({
    mutationFn: async () => {
      const response = await AiService.runDailyBriefingAutomation()
      return response.data
    },
    onSuccess: async (run) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: dailyAutomationQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["ai-daily-briefing"] }),
      ])
      if (run.status === "failed") {
        toast.error("Daily automation failed", {
          description: run.error ?? "Local AI could not create the briefing.",
        })
        return
      }
      toast.success("Daily briefing generated automatically")
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const runWeeklyMutation = useMutation({
    mutationFn: async () => {
      const response = await AiService.runWeeklyReviewAutomation()
      return response.data
    },
    onSuccess: async (run) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: weeklyAutomationQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["ai-weekly-review"] }),
        queryClient.invalidateQueries({ queryKey: ["ai-weekly-reviews"] }),
      ])
      if (run.status === "failed") {
        toast.error("Weekly automation failed", {
          description: run.error ?? "Local AI could not create the review.",
        })
        return
      }
      toast.success("Weekly review generated automatically")
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const daily = dailyQuery.data
  const weekly = weeklyQuery.data
  const dailyHasChanges = Boolean(
    daily &&
      (dailyEnabled !== daily.enabled ||
        dailyRunTime !== daily.run_time.slice(0, 5)),
  )
  const weeklyHasChanges = Boolean(
    weekly &&
      (weeklyEnabled !== weekly.enabled ||
        weeklyWeekday !== weekly.weekday ||
        weeklyRunTime !== weekly.run_time.slice(0, 5)),
  )

  if (dailyQuery.isPending || weeklyQuery.isPending) {
    return (
      <div
        className="space-y-6"
        role="status"
        aria-label="Loading AI automation"
      >
        <Skeleton className="h-48 rounded-2xl" />
        <div className="grid gap-6 xl:grid-cols-2">
          <Skeleton className="h-[32rem] rounded-xl" />
          <Skeleton className="h-[32rem] rounded-xl" />
        </div>
      </div>
    )
  }

  if (dailyQuery.error || weeklyQuery.error || !daily || !weekly) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertTitle>AI automation unavailable</AlertTitle>
        <AlertDescription>
          {getErrorMessage(dailyQuery.error ?? weeklyQuery.error)}
        </AlertDescription>
      </Alert>
    )
  }

  const activeSchedules = Number(daily.enabled) + Number(weekly.enabled)

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
              AI automation
            </h1>
            <p className="mt-3 text-muted-foreground">
              Schedule grounded daily briefings and weekly reviews while keeping
              every operational change under your control.
            </p>
          </div>
          <Badge variant={activeSchedules ? "default" : "secondary"}>
            {activeSchedules
              ? `${activeSchedules} schedule${activeSchedules === 1 ? "" : "s"} active`
              : "Schedules paused"}
          </Badge>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="py-5">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Sparkles className="size-4" />
              Next daily briefing
            </div>
            <p className="mt-2 font-semibold">
              {daily.enabled
                ? formatDateTime(daily.next_run_at, daily.timezone)
                : "Paused"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-5">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <CalendarDays className="size-4" />
              Next weekly review
            </div>
            <p className="mt-2 font-semibold">
              {weekly.enabled
                ? formatDateTime(weekly.next_run_at, weekly.timezone)
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
            <p className="mt-2 font-semibold">{daily.timezone}</p>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader className="border-b">
            <CardTitle>Daily briefing</CardTitle>
            <CardDescription>
              Creates at most one scheduled briefing per business day.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 py-6">
            <div className="flex items-start gap-3 rounded-xl border p-4">
              <Checkbox
                id="daily-automation-enabled"
                checked={dailyEnabled}
                onCheckedChange={(checked) => setDailyEnabled(checked === true)}
              />
              <div className="grid gap-1.5">
                <Label htmlFor="daily-automation-enabled">
                  Generate daily briefings automatically
                </Label>
                <p className="text-sm text-muted-foreground">
                  Uses the deterministic daily dashboard snapshot.
                </p>
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="daily-automation-time">Run time</Label>
              <Input
                className="max-w-48"
                id="daily-automation-time"
                type="time"
                value={dailyRunTime}
                onChange={(event) => setDailyRunTime(event.target.value)}
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                disabled={
                  !dailyHasChanges ||
                  updateDailyMutation.isPending ||
                  !dailyRunTime
                }
                onClick={() =>
                  updateDailyMutation.mutate({
                    enabled: dailyEnabled,
                    run_time: `${dailyRunTime}:00`,
                  })
                }
              >
                {updateDailyMutation.isPending ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <CalendarClock />
                )}
                Save daily schedule
              </Button>
              <Button
                variant="outline"
                disabled={runDailyMutation.isPending}
                onClick={() => runDailyMutation.mutate()}
              >
                {runDailyMutation.isPending ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <Play />
                )}
                {runDailyMutation.isPending ? "Running..." : "Run now"}
              </Button>
            </div>
            <div className="border-t pt-5">
              <p className="mb-3 text-sm font-medium">Latest daily run</p>
              <RunSummary
                emptyMessage="No daily automation runs yet."
                run={daily.last_run}
                timezone={daily.timezone}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b">
            <CardTitle>Weekly review</CardTitle>
            <CardDescription>
              Reviews the seven completed days ending before the scheduled run.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 py-6">
            <div className="flex items-start gap-3 rounded-xl border p-4">
              <Checkbox
                id="weekly-automation-enabled"
                checked={weeklyEnabled}
                onCheckedChange={(checked) =>
                  setWeeklyEnabled(checked === true)
                }
              />
              <div className="grid gap-1.5">
                <Label htmlFor="weekly-automation-enabled">
                  Generate weekly reviews automatically
                </Label>
                <p className="text-sm text-muted-foreground">
                  Uses the grounded seven-day trends snapshot and comparison.
                </p>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label>Run day</Label>
                <Select
                  value={String(weeklyWeekday)}
                  onValueChange={(value) => setWeeklyWeekday(Number(value))}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {weekdays.map((weekday, index) => (
                      <SelectItem key={weekday} value={String(index)}>
                        {weekday}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="weekly-automation-time">Run time</Label>
                <Input
                  id="weekly-automation-time"
                  type="time"
                  value={weeklyRunTime}
                  onChange={(event) => setWeeklyRunTime(event.target.value)}
                />
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                disabled={
                  !weeklyHasChanges ||
                  updateWeeklyMutation.isPending ||
                  !weeklyRunTime
                }
                onClick={() =>
                  updateWeeklyMutation.mutate({
                    enabled: weeklyEnabled,
                    weekday: weeklyWeekday,
                    run_time: `${weeklyRunTime}:00`,
                  })
                }
              >
                {updateWeeklyMutation.isPending ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <CalendarClock />
                )}
                Save weekly schedule
              </Button>
              <Button
                variant="outline"
                disabled={runWeeklyMutation.isPending}
                onClick={() => runWeeklyMutation.mutate()}
              >
                {runWeeklyMutation.isPending ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <Play />
                )}
                {runWeeklyMutation.isPending ? "Running..." : "Run now"}
              </Button>
            </div>
            <div className="border-t pt-5">
              <p className="mb-3 text-sm font-medium">Latest weekly run</p>
              <RunSummary
                emptyMessage="No weekly automation runs yet."
                run={weekly.last_run}
                timezone={weekly.timezone}
              />
            </div>
          </CardContent>
        </Card>
      </section>

      <Card className="border-emerald-500/25 bg-emerald-500/5">
        <CardHeader>
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-emerald-600" />
            <CardTitle>Automation guardrails</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-2 text-sm text-muted-foreground md:grid-cols-3">
            <li>Reads only deterministic daily and weekly operations data.</li>
            <li>Saves every AI result with its original source snapshot.</li>
            <li>Never changes products, inventory, sales, or actions.</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
