"use client"

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "@/components/ui/accordion"
import { AlertCircle, CheckCircle2 } from "lucide-react"

import type { ToolExecution } from "./chat-message"
import { cn } from "@/lib/utils"

interface ToolExecutionsAccordionProps {
  tools: ToolExecution[]
  className?: string
}

export function ToolExecutionsAccordion({
  tools,
  className
}: ToolExecutionsAccordionProps) {
  if (!tools || tools.length === 0) return null

  const toolsByIteration = tools.reduce(
    (acc, tool) => {
      if (!acc[tool.iteration]) {
        acc[tool.iteration] = []
      }
      acc[tool.iteration].push(tool)
      return acc
    },
    {} as Record<number, ToolExecution[]>
  )

  return (
    <div className={cn("mt-3 space-y-2", className)}>
      <Accordion type="multiple" className="w-full space-y-3">
        {Object.entries(toolsByIteration)
          .sort(([a], [b]) => parseInt(a) - parseInt(b))
          .map(([iteration, iterationTools]) => (
            <div key={iteration} className="space-y-2">
              {iterationTools.length > 1 && (
                <div className="text-xs text-muted-foreground font-medium">
                  Step {iteration}
                </div>
              )}
              {iterationTools.map((tool, index) => (
                <ToolExecutionCard
                  key={`${iteration}-${index}`}
                  tool={tool}
                  iteration={parseInt(iteration)}
                  index={index}
                />
              ))}
            </div>
          ))}
      </Accordion>
    </div>
  )
}

interface ToolExecutionCardProps {
  tool: ToolExecution
  iteration: number
  index: number
}

function ToolExecutionCard({ tool, iteration, index }: ToolExecutionCardProps) {
  const isSuccess = tool.status === "success"
  const hasResult = tool.result !== undefined && tool.result !== null
  const hasError = tool.error !== undefined

  return (
    <AccordionItem
      value={`${tool.tool_name}-${iteration}-${index}`}
      className="rounded-md border bg-muted/30 p-3"
    >
      <AccordionTrigger className="p-0 hover:no-underline">
        <div className="flex items-center gap-2">
          {isSuccess ? (
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          ) : (
            <AlertCircle className="h-4 w-4 text-destructive" />
          )}
          <span className="font-mono text-sm font-medium">{tool.tool_name}</span>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs",
              isSuccess
                ? "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400"
                : "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400"
            )}
          >
            {tool.status}
          </span>
        </div>
      </AccordionTrigger>
      <AccordionContent className="p-0">
        <div className="pt-4">
          {tool.tool_args && Object.keys(tool.tool_args).length > 0 && (
            <div className="space-y-1">
              <div className="text-xs font-medium text-muted-foreground">
                Request:
              </div>
              <div className="rounded border bg-background p-2">
                <pre className="overflow-x-auto whitespace-pre-wrap text-xs">
                  {JSON.stringify(tool.tool_args, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {hasResult && (
            <div className="space-y-1">
              <div className="text-xs font-medium text-muted-foreground">
                Response:
              </div>
              <div className="max-h-60 overflow-y-auto rounded border bg-background p-2">
                <pre className="overflow-x-auto whitespace-pre-wrap text-xs">
                  {typeof tool.result === "string"
                    ? tool.result
                    : JSON.stringify(tool.result, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {hasError && (
            <div className="space-y-1">
              <div className="text-xs font-medium text-destructive">Error:</div>
              <div className="rounded border border-destructive/20 bg-destructive/10 p-2">
                <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-destructive">
                  {tool.error}
                </pre>
              </div>
            </div>
          )}
        </div>
      </AccordionContent>
    </AccordionItem>
  )
}
