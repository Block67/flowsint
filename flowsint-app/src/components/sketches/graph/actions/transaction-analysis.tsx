import { useCallback, useMemo, useState } from 'react'
import { useParams } from '@tanstack/react-router'
import { ArrowDownRight, ArrowUpLeft, Loader2, ShieldAlert, Waypoints, X } from 'lucide-react'
import { useGraphStore } from '@/stores/graph-store'
import { useGraphControls } from '@/stores/graph-controls-store'
import { useTransactionAnalysisStore } from '@/stores/transaction-analysis-store'
import { ToolbarButton } from '../../toolbar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ResizableContainer } from '@/components/ui/resizable-container'
import { cn } from '@/lib/utils'
import type { TraceDirection, TransactionAlert, TransactionAlertType } from '@/types'

const ALERT_LABELS: Record<TransactionAlertType, string> = {
  fan_out: 'Fan-out',
  fan_in: 'Fan-in',
  pass_through: 'Pass-through',
  structuring: 'Structuring',
  cycle: 'Cycle'
}

const formatEpoch = (epoch: number | null | undefined) =>
  epoch ? new Date(epoch * 1000).toLocaleString() : '—'

const formatDetail = (key: string, value: unknown) => {
  if (value === null || value === undefined) return '—'
  if ((key === 'start' || key === 'end') && typeof value === 'number') return formatEpoch(value)
  if (typeof value === 'number')
    return value.toLocaleString(undefined, { maximumFractionDigits: 4 })
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function useHighlight() {
  const setHighlightedNodes = useGraphStore((s) => s.setHighlightedNodes)
  const setPath = useGraphStore((s) => s.setPath)
  const zoomToSelection = useGraphControls((s) => s.zoomToSelection)
  return useCallback(
    (nodeIds: string[]) => {
      setPath(null)
      setHighlightedNodes(nodeIds)
      if (nodeIds.length) zoomToSelection()
    },
    [setPath, setHighlightedNodes, zoomToSelection]
  )
}

export function TransactionAnalysisButtons() {
  const { id: sketchId } = useParams({ strict: false })
  const selectedNodes = useGraphStore((s) => s.selectedNodes)
  const isLoading = useTransactionAnalysisStore((s) => s.isLoading)
  const mode = useTransactionAnalysisStore((s) => s.mode)
  const runDetection = useTransactionAnalysisStore((s) => s.runDetection)
  const runTrace = useTransactionAnalysisStore((s) => s.runTrace)
  const highlight = useHighlight()

  const canTrace = selectedNodes.length === 1

  const handleDetect = useCallback(async () => {
    if (!sketchId) return
    await runDetection(sketchId)
  }, [sketchId, runDetection])

  const handleTrace = useCallback(async () => {
    if (!sketchId || !canTrace) return
    const trace = await runTrace(sketchId, selectedNodes[0].id)
    if (trace) highlight(Object.keys(trace.nodes))
  }, [sketchId, canTrace, selectedNodes, runTrace, highlight])

  const spinner = <Loader2 className="h-4 w-4 opacity-70 animate-spin" />
  return (
    <>
      <ToolbarButton
        icon={
          isLoading && mode === 'alerts' ? spinner : <ShieldAlert className="h-4 w-4 opacity-70" />
        }
        tooltip="Detect suspicious transaction patterns"
        onClick={handleDetect}
        disabled={!sketchId || isLoading}
        toggled={mode === 'alerts'}
      />
      <ToolbarButton
        icon={
          isLoading && mode === 'trace' ? spinner : <Waypoints className="h-4 w-4 opacity-70" />
        }
        tooltip="Trace funds from the selected account"
        onClick={handleTrace}
        disabled={!sketchId || !canTrace || isLoading}
        toggled={mode === 'trace'}
      />
    </>
  )
}

function AlertItem({
  alert,
  active,
  onSelect
}: {
  alert: TransactionAlert
  active: boolean
  onSelect: () => void
}) {
  return (
    <div className={cn('rounded border', active && 'border-primary bg-muted/50')}>
      <button onClick={onSelect} className="w-full text-left px-2 py-1.5 hover:bg-muted rounded">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="px-1 shrink-0">
            {ALERT_LABELS[alert.type] ?? alert.type}
          </Badge>
          <span className="text-xs text-muted-foreground ml-auto shrink-0">
            {Math.round(alert.score * 100)}%
          </span>
        </div>
        <p className="text-sm mt-1 break-words">{alert.title}</p>
      </button>
      {active && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 px-2 pb-2 text-xs">
          {Object.entries(alert.details)
            .filter(([key]) => key !== 'account')
            .map(([key, value]) => (
              <div key={key} className="contents">
                <dt className="text-muted-foreground">{key.replace(/_/g, ' ')}</dt>
                <dd className="truncate">{formatDetail(key, value)}</dd>
              </div>
            ))}
        </dl>
      )}
    </div>
  )
}

function AlertsView({ sketchId }: { sketchId: string }) {
  const alerts = useTransactionAnalysisStore((s) => s.alerts)
  const params = useTransactionAnalysisStore((s) => s.params)
  const setParams = useTransactionAnalysisStore((s) => s.setParams)
  const runDetection = useTransactionAnalysisStore((s) => s.runDetection)
  const isLoading = useTransactionAnalysisStore((s) => s.isLoading)
  const highlight = useHighlight()
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const [threshold, setThreshold] = useState(params.structuring_threshold?.toString() ?? '')
  const [currency, setCurrency] = useState(params.structuring_currency ?? '')

  const handleRun = useCallback(async () => {
    const value = parseFloat(threshold.replace(/\s/g, '').replace(',', '.'))
    setParams({
      ...params,
      structuring_threshold: Number.isFinite(value) && value > 0 ? value : null,
      structuring_currency: currency.trim() || null
    })
    setActiveIndex(null)
    await runDetection(sketchId)
  }, [threshold, currency, params, setParams, runDetection, sketchId])

  const handleSelect = useCallback(
    (index: number, alert: TransactionAlert) => {
      const next = activeIndex === index ? null : index
      setActiveIndex(next)
      highlight(next === null ? [] : alert.node_ids)
    },
    [activeIndex, highlight]
  )

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const a of alerts ?? []) c[a.type] = (c[a.type] ?? 0) + 1
    return c
  }, [alerts])

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 border-b space-y-2 shrink-0">
        <div className="grid grid-cols-[1fr_70px] gap-2">
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Structuring threshold</Label>
            <Input
              className="h-7 text-xs"
              placeholder="e.g. 1 000 000"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Currency</Label>
            <Input
              className="h-7 text-xs"
              placeholder="XOF"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
            />
          </div>
        </div>
        <Button size="sm" className="h-7 w-full" onClick={handleRun} disabled={isLoading}>
          {isLoading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Run detection
        </Button>
        {alerts && alerts.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {Object.entries(counts).map(([type, count]) => (
              <Badge key={type} variant="outline" className="px-1 text-[10px]">
                {ALERT_LABELS[type as TransactionAlertType] ?? type}: {count}
              </Badge>
            ))}
          </div>
        )}
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-1.5">
        {alerts?.length === 0 && (
          <p className="text-sm text-muted-foreground p-2">
            No suspicious pattern found in this sketch&apos;s transactions.
          </p>
        )}
        {alerts?.map((alert, index) => (
          <AlertItem
            key={`${alert.type}-${index}`}
            alert={alert}
            active={activeIndex === index}
            onSelect={() => handleSelect(index, alert)}
          />
        ))}
      </div>
    </div>
  )
}

function TraceView({ sketchId }: { sketchId: string }) {
  const trace = useTransactionAnalysisStore((s) => s.trace)
  const traceNodeId = useTransactionAnalysisStore((s) => s.traceNodeId)
  const direction = useTransactionAnalysisStore((s) => s.traceDirection)
  const maxHops = useTransactionAnalysisStore((s) => s.traceMaxHops)
  const runTrace = useTransactionAnalysisStore((s) => s.runTrace)
  const isLoading = useTransactionAnalysisStore((s) => s.isLoading)
  const setCurrentNodeId = useGraphStore((s) => s.setCurrentNodeId)
  const highlight = useHighlight()

  const rerun = useCallback(
    async (dir: TraceDirection, hops: number) => {
      if (!traceNodeId) return
      const result = await runTrace(sketchId, traceNodeId, dir, hops)
      if (result) highlight(Object.keys(result.nodes))
    },
    [traceNodeId, runTrace, sketchId, highlight]
  )

  const reached = useMemo(
    () =>
      Object.entries(trace?.nodes ?? {})
        .filter(([id]) => id !== trace?.start_node_id)
        .sort(([, a], [, b]) => a.hops - b.hops || (a.first_seen ?? 0) - (b.first_seen ?? 0)),
    [trace]
  )
  const startLabel = trace ? trace.nodes[trace.start_node_id]?.label : null

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 border-b space-y-2 shrink-0">
        <p className="text-xs text-muted-foreground truncate">
          From <span className="text-foreground font-medium">{startLabel ?? traceNodeId}</span>
        </p>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant={direction === 'downstream' ? 'secondary' : 'ghost'}
            className="h-7 text-xs"
            onClick={() => rerun('downstream', maxHops)}
            disabled={isLoading}
          >
            <ArrowDownRight className="h-3.5 w-3.5" /> Where it went
          </Button>
          <Button
            size="sm"
            variant={direction === 'upstream' ? 'secondary' : 'ghost'}
            className="h-7 text-xs"
            onClick={() => rerun('upstream', maxHops)}
            disabled={isLoading}
          >
            <ArrowUpLeft className="h-3.5 w-3.5" /> Where it came from
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground">Max hops</Label>
          {[2, 4, 6, 8].map((h) => (
            <Button
              key={h}
              size="sm"
              variant={maxHops === h ? 'secondary' : 'ghost'}
              className="h-6 w-6 p-0 text-xs"
              onClick={() => rerun(direction, h)}
              disabled={isLoading}
            >
              {h}
            </Button>
          ))}
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-1">
        {trace && reached.length === 0 && (
          <p className="text-sm text-muted-foreground p-2">
            No transfer found {direction === 'downstream' ? 'after' : 'before'} this account in time
            order.
          </p>
        )}
        {reached.map(([id, info]) => (
          <button
            key={id}
            onClick={() => setCurrentNodeId(id)}
            className="w-full text-left px-2 py-1.5 rounded hover:bg-muted flex items-center gap-2"
          >
            <Badge variant="outline" className="px-1 shrink-0 text-[10px]">
              {info.hops} hop{info.hops > 1 ? 's' : ''}
            </Badge>
            <div className="min-w-0 flex-1">
              <div className="text-sm truncate">{info.label ?? id}</div>
              <div className="text-[10px] text-muted-foreground">
                {direction === 'downstream' ? 'reached' : 'sent'} {formatEpoch(info.first_seen)}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

export function TransactionAnalysisPanel() {
  const { id: sketchId } = useParams({ strict: false })
  const mode = useTransactionAnalysisStore((s) => s.mode)
  const error = useTransactionAnalysisStore((s) => s.error)
  const trace = useTransactionAnalysisStore((s) => s.trace)
  const close = useTransactionAnalysisStore((s) => s.close)
  const setHighlightedNodes = useGraphStore((s) => s.setHighlightedNodes)

  const handleClose = useCallback(() => {
    close()
    setHighlightedNodes([])
  }, [close, setHighlightedNodes])

  if (!mode || !sketchId) return null

  const title =
    mode === 'alerts'
      ? 'Suspicious patterns'
      : `Fund trace${trace ? ` (${Object.keys(trace.nodes).length - 1} accounts)` : ''}`

  return (
    <div className="absolute top-2 right-2 z-50">
      <ResizableContainer
        defaultWidth={320}
        defaultHeight={460}
        minWidth={240}
        minHeight={200}
        maxWidth={560}
        maxHeight={800}
        handles={['se', 'sw']}
        storageKey="resizable-transaction-analysis-panel"
        className="rounded-xl border bg-card shadow-lg"
      >
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-between px-3 py-2 border-b shrink-0">
            <span className="text-sm font-medium truncate">{title}</span>
            <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0" onClick={handleClose}>
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
          {error && <p className="text-xs text-destructive px-3 py-2 border-b">{error}</p>}
          <div className="flex-1 min-h-0">
            {mode === 'alerts' ? (
              <AlertsView sketchId={sketchId} />
            ) : (
              <TraceView sketchId={sketchId} />
            )}
          </div>
        </div>
      </ResizableContainer>
    </div>
  )
}
