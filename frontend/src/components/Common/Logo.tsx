import { Link } from "@tanstack/react-router"
import { Gauge } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const mark = (
    <span className="flex size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
      <Gauge className="size-4" />
    </span>
  )
  const wordmark = (
    <span className="text-lg font-semibold tracking-tight">OpsPilot</span>
  )

  let content: ReactNode
  if (variant === "responsive") {
    content = (
      <>
        <span
          className={cn(
            "flex items-center gap-2.5 group-data-[collapsible=icon]:hidden",
            className,
          )}
        >
          {mark}
          {wordmark}
        </span>
        <span className="hidden group-data-[collapsible=icon]:block">
          {mark}
        </span>
      </>
    )
  } else if (variant === "icon") {
    content = <span className={className}>{mark}</span>
  } else {
    content = (
      <span className={cn("flex items-center gap-2.5", className)}>
        {mark}
        {wordmark}
      </span>
    )
  }

  if (!asLink) {
    return content
  }

  return (
    <Link to="/" aria-label="OpsPilot dashboard">
      {content}
    </Link>
  )
}
