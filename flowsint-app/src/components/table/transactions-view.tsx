import { useCallback, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from '@tanstack/react-router'
import { useVirtualizer } from '@tanstack/react-virtual'
import { ArrowDown, ArrowUp, Search } from 'lucide-react'
import { useGraphStore } from '@/stores/graph-store'
import { transactionAnalyticsService } from '@/api/transaction-analytics-service'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { cn } from '@/lib/utils'
import type { GraphEdge, TransactionAccountSummary } from '@/types'

const ROW_HEIGHT = 36

type SortKey = 'date' | 'amount'

interface TransactionRow {
  edge: GraphEdge
  from: string
  to: string
  time: number | null
}

const formatDate = (time: number | null) => (time ? new Date(time).toLocaleString() : '—')

const formatNumber = (value: number) =>
  value.toLocaleString(undefined, { maximumFractionDigits: 8 })

function SortHeader({
  label,
  active,
  descending,
  onClick,
  className
}: {
  label: string
  active: boolean
  descending: boolean
  onClick: () => void
  className?: string
}) {
  const Icon = descending ? ArrowDown : ArrowUp
  return (
    <button onClick={onClick} className={cn('flex items-center gap-1 font-medium', className)}>
      {label}
      {active && <Icon className="h-3 w-3" />}
    </button>
  )
}

function TransactionsList() {
  const edges = useGraphStore((s) => s.filteredEdges)
  const nodesMapping = useGraphStore((s) => s.nodesMapping)
  const setCurrentNodeId = useGraphStore((s) => s.setCurrentNodeId)
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('date')
  const [descending, setDescending] = useState(true)
  const parentRef = useRef<HTMLDivElement>(null)

  const rows = useMemo(() => {
    const query = search.trim().toLowerCase()
    const result: TransactionRow[] = []
    for (const edge of edges) {
      if (edge.type !== 'transaction') continue
      const from = nodesMapping.get(edge.source)?.nodeLabel ?? edge.source
      const to = nodesMapping.get(edge.target)?.nodeLabel ?? edge.target
      if (query && !`${from} ${to} ${edge.caption ?? ''}`.toLowerCase().includes(query)) {
        continue
      }
      result.push({ edge, from, to, time: edge.date ? Date.parse(edge.date) : null })
    }
    const sign = descending ? -1 : 1
    return result.sort((a, b) =>
      sortKey === 'date'
        ? sign * ((a.time ?? 0) - (b.time ?? 0))
        : sign * ((a.edge.weight ?? 0) - (b.edge.weight ?? 0))
    )
  }, [edges, nodesMapping, search, sortKey, descending])

  const toggleSort = useCallback(
    (key: SortKey) => {
      if (key === sortKey) setDescending((d) => !d)
      else {
        setSortKey(key)
        setDescending(true)
      }
    },
    [sortKey]
  )

  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10
  })

  return (
    <div className="flex flex-col h-full gap-3">
      <div className="flex items-center gap-3">
        <div className="relative w-72">
          <Search className="absolute left-2 top-2 h-4 w-4 text-muted-foreground" />
          <Input
            className="h-8 pl-8"
            placeholder="Search account or amount…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span className="text-xs text-muted-foreground">{rows.length} transactions</span>
      </div>
      <div className="grid grid-cols-[180px_1fr_1fr_160px] gap-3 px-3 text-xs text-muted-foreground border-b pb-2">
        <SortHeader
          label="Date"
          active={sortKey === 'date'}
          descending={descending}
          onClick={() => toggleSort('date')}
        />
        <span className="font-medium">From</span>
        <span className="font-medium">To</span>
        <SortHeader
          label="Amount"
          active={sortKey === 'amount'}
          descending={descending}
          onClick={() => toggleSort('amount')}
          className="justify-end"
        />
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground px-3">
          No transactions. Import a CSV/Excel statement or run a crypto enricher.
        </p>
      ) : (
        <div ref={parentRef} className="flex-1 min-h-0 overflow-auto">
          <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
            {virtualizer.getVirtualItems().map((item) => {
              const row = rows[item.index]
              return (
                <div
                  key={row.edge.id}
                  className="absolute left-0 right-0 grid grid-cols-[180px_1fr_1fr_160px] gap-3 px-3 items-center text-sm border-b hover:bg-muted/50"
                  style={{ top: item.start, height: ROW_HEIGHT }}
                >
                  <span className="text-xs text-muted-foreground">{formatDate(row.time)}</span>
                  <button
                    className="truncate text-left hover:underline"
                    onClick={() => setCurrentNodeId(row.edge.source)}
                  >
                    {row.from}
                  </button>
                  <button
                    className="truncate text-left hover:underline"
                    onClick={() => setCurrentNodeId(row.edge.target)}
                  >
                    {row.to}
                  </button>
                  <span className="text-right tabular-nums">{row.edge.caption ?? '—'}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function AccountsList() {
  const { id: sketchId } = useParams({ strict: false })
  const setCurrentNodeId = useGraphStore((s) => s.setCurrentNodeId)
  const { data, isLoading, error } = useQuery({
    queryKey: ['transaction-accounts', sketchId],
    queryFn: () => transactionAnalyticsService.accounts(sketchId as string, 500),
    enabled: Boolean(sketchId)
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    )
  }
  if (error) {
    return <p className="text-sm text-destructive">{(error as Error).message}</p>
  }
  if (!data?.length) {
    return <p className="text-sm text-muted-foreground">No transactions in this sketch yet.</p>
  }

  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-muted-foreground border-b">
          <tr className="text-left">
            <th className="py-2 px-3 font-medium">Account</th>
            <th className="py-2 px-3 font-medium text-right">Received</th>
            <th className="py-2 px-3 font-medium text-right">Sent</th>
            <th className="py-2 px-3 font-medium text-right">Net</th>
            <th className="py-2 px-3 font-medium text-right">Senders</th>
            <th className="py-2 px-3 font-medium text-right">Recipients</th>
            <th className="py-2 px-3 font-medium">Active</th>
          </tr>
        </thead>
        <tbody>
          {data.map((a: TransactionAccountSummary) => (
            <tr key={`${a.node_id}-${a.currency}`} className="border-b hover:bg-muted/50">
              <td className="py-1.5 px-3 max-w-[280px]">
                <button
                  className="truncate block text-left hover:underline max-w-full"
                  onClick={() => setCurrentNodeId(a.node_id)}
                >
                  {a.label ?? a.node_id}
                </button>
              </td>
              <td className="py-1.5 px-3 text-right tabular-nums">
                {formatNumber(a.inflow)} {a.currency ?? ''}
              </td>
              <td className="py-1.5 px-3 text-right tabular-nums">
                {formatNumber(a.outflow)} {a.currency ?? ''}
              </td>
              <td
                className={cn(
                  'py-1.5 px-3 text-right tabular-nums',
                  a.net < 0 ? 'text-red-600' : 'text-green-600'
                )}
              >
                {formatNumber(a.net)}
              </td>
              <td className="py-1.5 px-3 text-right">{a.senders}</td>
              <td className="py-1.5 px-3 text-right">{a.receivers}</td>
              <td className="py-1.5 px-3 text-xs text-muted-foreground whitespace-nowrap">
                {a.first_seen ? new Date(a.first_seen * 1000).toLocaleDateString() : '—'}
                {' → '}
                {a.last_seen ? new Date(a.last_seen * 1000).toLocaleDateString() : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function TransactionsView() {
  const [tab, setTab] = useState<'transactions' | 'accounts'>('transactions')
  return (
    <div className="w-full h-full flex flex-col p-4 px-6 gap-3">
      <ToggleGroup
        type="single"
        value={tab}
        onValueChange={(v) => v && setTab(v as typeof tab)}
        className="self-start"
      >
        <ToggleGroupItem value="transactions" className="h-7 px-3 text-xs">
          Transactions
        </ToggleGroupItem>
        <ToggleGroupItem value="accounts" className="h-7 px-3 text-xs">
          Accounts
        </ToggleGroupItem>
      </ToggleGroup>
      <div className="flex-1 min-h-0 flex flex-col">
        {tab === 'transactions' ? <TransactionsList /> : <AccountsList />}
      </div>
    </div>
  )
}
