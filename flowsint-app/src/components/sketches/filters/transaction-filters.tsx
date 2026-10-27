import { useState } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Filters } from '@/types/filter'

type TransactionFiltersProps = {
  filters: Filters
  setFilters: (filters: Filters) => void
}

const TransactionFilters = ({ filters, setFilters }: TransactionFiltersProps) => {
  const current = filters.transactions ?? {}
  const storedMinAmount = current.minAmount?.toString() ?? ''
  const [minAmount, setMinAmount] = useState(storedMinAmount)
  // Keep the text box in sync when filters are reset elsewhere
  const [prevStoredMinAmount, setPrevStoredMinAmount] = useState(storedMinAmount)
  if (storedMinAmount !== prevStoredMinAmount) {
    setPrevStoredMinAmount(storedMinAmount)
    setMinAmount(storedMinAmount)
  }

  const update = (patch: Partial<NonNullable<Filters['transactions']>>) =>
    setFilters({ ...filters, transactions: { ...current, ...patch } })

  const commitMinAmount = () => {
    const value = parseFloat(minAmount.replace(/\s/g, '').replace(',', '.'))
    update({ minAmount: Number.isFinite(value) && value > 0 ? value : null })
  }

  const isActive = Boolean(current.from || current.to || current.minAmount)

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="opacity-90 text-sm">Filter transactions</p>
        {isActive && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs"
            onClick={() => setFilters({ ...filters, transactions: undefined })}
          >
            Clear
          </Button>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">From</Label>
          <Input
            type="date"
            className="h-8 text-xs"
            value={current.from ?? ''}
            onChange={(e) => update({ from: e.target.value || null })}
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">To</Label>
          <Input
            type="date"
            className="h-8 text-xs"
            value={current.to ?? ''}
            onChange={(e) => update({ to: e.target.value || null })}
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Min amount</Label>
          <Input
            className="h-8 text-xs"
            placeholder="0"
            value={minAmount}
            onChange={(e) => setMinAmount(e.target.value)}
            onBlur={commitMinAmount}
            onKeyDown={(e) => e.key === 'Enter' && commitMinAmount()}
          />
        </div>
      </div>
      <p className="text-[11px] text-muted-foreground">
        Undated transactions are hidden while a period is set. Amounts are compared in USD when
        known, otherwise in the transaction currency.
      </p>
    </div>
  )
}

export default TransactionFilters
