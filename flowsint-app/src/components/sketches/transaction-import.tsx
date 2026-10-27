import { useCallback, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { toast } from 'sonner'
import { sketchService } from '@/api/sketch-service'
import { useGraphControls } from '@/stores/graph-controls-store'
import type {
  TransactionAccountSide,
  TransactionAccountType,
  TransactionChannel,
  TransactionMapping,
  TransactionPreview,
  TransactionTableAnalysis
} from '@/types'

const NONE = '__none__'

const ACCOUNT_TYPES: { value: TransactionAccountType; label: string }[] = [
  { value: 'MobileMoneyAccount', label: 'Mobile money' },
  { value: 'BankAccount', label: 'Bank account' },
  { value: 'CryptoWallet', label: 'Crypto wallet' },
  { value: 'CreditCard', label: 'Card' },
  { value: 'Merchant', label: 'Merchant' }
]

const CHANNEL_BY_ACCOUNT: Partial<Record<TransactionAccountType, TransactionChannel>> = {
  MobileMoneyAccount: 'mobile_money',
  BankAccount: 'bank',
  CryptoWallet: 'crypto',
  CreditCard: 'card'
}

const CHANNELS: TransactionChannel[] = ['mobile_money', 'bank', 'card', 'crypto', 'cash', 'other']

interface SideState {
  account_type: TransactionAccountType
  column: string
  value: string
  provider: string
  provider_column: string
  holder_column: string
  country: string
}

const emptySide = (account_type: TransactionAccountType, column = ''): SideState => ({
  account_type,
  column,
  value: '',
  provider: '',
  provider_column: '',
  holder_column: '',
  country: ''
})

const orNull = (v: string) => (v.trim() ? v.trim() : null)

const toAccountSide = (side: SideState, useValue: boolean): TransactionAccountSide => ({
  account_type: side.account_type,
  column: useValue ? null : orNull(side.column),
  value: useValue ? orNull(side.value) : null,
  provider: orNull(side.provider),
  provider_column: orNull(side.provider_column),
  holder_column: orNull(side.holder_column),
  country: orNull(side.country)
})

interface ColumnSelectProps {
  label: string
  value: string
  headers: string[]
  onChange: (value: string) => void
}

function ColumnSelect({ label, value, headers, onChange }: ColumnSelectProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Select value={value || NONE} onValueChange={(v) => onChange(v === NONE ? '' : v)}>
        <SelectTrigger className="h-8 w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NONE}>— none —</SelectItem>
          {headers.map((h) => (
            <SelectItem key={h} value={h}>
              {h}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

interface TextFieldProps {
  label: string
  value: string
  placeholder?: string
  onChange: (value: string) => void
}

function TextField({ label, value, placeholder, onChange }: TextFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input
        className="h-8"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}

interface AccountSideEditorProps {
  title: string
  side: SideState
  headers: string[]
  useValue: boolean
  onChange: (side: SideState) => void
}

function AccountSideEditor({ title, side, headers, useValue, onChange }: AccountSideEditorProps) {
  const set = (patch: Partial<SideState>) => onChange({ ...side, ...patch })
  return (
    <div className="flex flex-col gap-3 rounded-md border p-3">
      <p className="text-sm font-medium">{title}</p>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs text-muted-foreground">Account type</Label>
        <Select
          value={side.account_type}
          onValueChange={(v) => set({ account_type: v as TransactionAccountType })}
        >
          <SelectTrigger className="h-8 w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ACCOUNT_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {useValue ? (
        <TextField
          label="Account identifier (number, IBAN, address…)"
          value={side.value}
          onChange={(value) => set({ value })}
        />
      ) : (
        <ColumnSelect
          label="Identifier column"
          value={side.column}
          headers={headers}
          onChange={(column) => set({ column })}
        />
      )}
      <div className="grid grid-cols-2 gap-2">
        <TextField
          label="Provider / bank"
          value={side.provider}
          placeholder="Orange Money, Wave…"
          onChange={(provider) => set({ provider })}
        />
        <TextField
          label="Country (ISO)"
          value={side.country}
          placeholder="SN, CI…"
          onChange={(country) => set({ country })}
        />
      </div>
      {!useValue && (
        <div className="grid grid-cols-2 gap-2">
          <ColumnSelect
            label="Provider column"
            value={side.provider_column}
            headers={headers}
            onChange={(provider_column) => set({ provider_column })}
          />
          <ColumnSelect
            label="Holder name column"
            value={side.holder_column}
            headers={headers}
            onChange={(holder_column) => set({ holder_column })}
          />
        </div>
      )}
    </div>
  )
}

interface TransactionImportProps {
  sketchId: string
  file: File
  analysis: TransactionTableAnalysis
  onSuccess: () => void
  onCancel: () => void
}

export function TransactionImport({
  sketchId,
  file,
  analysis,
  onSuccess,
  onCancel
}: TransactionImportProps) {
  const { headers, suggested_columns: suggested } = analysis
  const col = (key: string) => suggested[key] ?? ''

  const [mode, setMode] = useState<'ledger' | 'statement'>(analysis.suggested_mode)
  const [source, setSource] = useState(emptySide('MobileMoneyAccount', col('source')))
  const [target, setTarget] = useState(emptySide('MobileMoneyAccount', col('target')))
  const [owner, setOwner] = useState(emptySide('BankAccount'))
  const [counterparty, setCounterparty] = useState(
    emptySide('Merchant', col('counterparty') || col('description'))
  )
  const [columns, setColumns] = useState({
    transaction_id: col('transaction_id'),
    date: col('date'),
    amount: col('amount'),
    debit: col('debit'),
    credit: col('credit'),
    direction: col('direction'),
    currency: col('currency'),
    fees: col('fees'),
    status: col('status'),
    description: col('description')
  })
  const [currency, setCurrency] = useState('')
  const [channel, setChannel] = useState('')
  const [dayFirst, setDayFirst] = useState(true)
  const [decimalSeparator, setDecimalSeparator] = useState<string>(NONE)

  const [preview, setPreview] = useState<TransactionPreview | null>(null)
  const [previewedKey, setPreviewedKey] = useState<string | null>(null)
  const [isChecking, setIsChecking] = useState(false)
  const [isImporting, setIsImporting] = useState(false)

  const refetchGraph = useGraphControls((s) => s.refetchGraph)
  const regenerateLayout = useGraphControls((s) => s.regenerateLayout)
  const currentLayoutType = useGraphControls((s) => s.currentLayoutType)

  const setColumn = (key: keyof typeof columns) => (value: string) =>
    setColumns((prev) => ({ ...prev, [key]: value }))

  const firstAccountType = mode === 'ledger' ? source.account_type : owner.account_type
  const effectiveChannel = (channel ||
    CHANNEL_BY_ACCOUNT[firstAccountType] ||
    null) as TransactionChannel | null

  const mapping: TransactionMapping = useMemo(() => {
    const common = {
      mode,
      transaction_id_column: orNull(columns.transaction_id),
      date_column: orNull(columns.date),
      day_first: dayFirst,
      amount_column: orNull(columns.amount),
      currency_column: orNull(columns.currency),
      currency: orNull(currency),
      fees_column: orNull(columns.fees),
      status_column: orNull(columns.status),
      description_column: orNull(columns.description),
      decimal_separator: decimalSeparator === NONE ? null : (decimalSeparator as ',' | '.'),
      channel: effectiveChannel
    }
    if (mode === 'ledger') {
      return {
        ...common,
        source: toAccountSide(source, false),
        target: toAccountSide(target, false)
      }
    }
    return {
      ...common,
      owner: toAccountSide(owner, true),
      counterparty: toAccountSide(counterparty, false),
      debit_column: orNull(columns.debit),
      credit_column: orNull(columns.credit),
      direction_column: orNull(columns.direction)
    }
  }, [
    mode,
    columns,
    currency,
    dayFirst,
    decimalSeparator,
    effectiveChannel,
    source,
    target,
    owner,
    counterparty
  ])

  const mappingKey = useMemo(() => JSON.stringify(mapping), [mapping])
  const previewIsCurrent = preview !== null && previewedKey === mappingKey
  const canImport =
    preview !== null && previewedKey === mappingKey && preview.valid_rows > 0 && !isImporting

  const handleCheck = useCallback(async () => {
    setIsChecking(true)
    try {
      const result = await sketchService.previewTransactionImport(sketchId, file, mapping)
      setPreview(result)
      setPreviewedKey(mappingKey)
    } catch (error) {
      setPreview(null)
      toast.error((error as Error)?.message)
    } finally {
      setIsChecking(false)
    }
  }, [sketchId, file, mapping, mappingKey])

  const handleImport = useCallback(async () => {
    setIsImporting(true)
    try {
      const result = await sketchService.executeTransactionImport(sketchId, file, mapping)
      refetchGraph()
      toast('Import successful !', {
        duration: 6000,
        description: `${result.transactions_imported} transactions between ${result.accounts_imported} accounts were imported${result.rows_failed ? `, ${result.rows_failed} rows skipped` : ''}.`,
        action: {
          label: 'Beautify layout',
          onClick: () => regenerateLayout(currentLayoutType)
        }
      })
      onSuccess()
    } catch (error) {
      toast.error((error as Error)?.message)
    } finally {
      setIsImporting(false)
    }
  }, [sketchId, file, mapping, refetchGraph, regenerateLayout, currentLayoutType, onSuccess])

  const sampleRows = analysis.sample_rows.slice(0, 5)

  return (
    <div className="flex flex-col grow overflow-hidden gap-4">
      <div className="flex items-center justify-between gap-4 shrink-0">
        <div className="min-w-0">
          <p className="font-medium truncate">{file.name}</p>
          <p className="text-xs text-muted-foreground">
            {analysis.total_rows} rows · {headers.length} columns
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground">File layout</Label>
          <Select value={mode} onValueChange={(v) => setMode(v as 'ledger' | 'statement')}>
            <SelectTrigger className="h-8 w-[260px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ledger">Ledger — sender & recipient per row</SelectItem>
              <SelectItem value="statement">Statement — one account&apos;s history</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex flex-col gap-4 grow overflow-auto pr-1">
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-xs">
            <thead className="bg-muted/50">
              <tr>
                {headers.map((h) => (
                  <th key={h} className="px-2 py-1.5 text-left font-medium whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sampleRows.map((row, i) => (
                <tr key={i} className="border-t">
                  {headers.map((h) => (
                    <td key={h} className="px-2 py-1 whitespace-nowrap text-muted-foreground">
                      {row[h] ?? ''}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          {mode === 'ledger' ? (
            <>
              <AccountSideEditor
                title="Sender (money out)"
                side={source}
                headers={headers}
                useValue={false}
                onChange={setSource}
              />
              <AccountSideEditor
                title="Recipient (money in)"
                side={target}
                headers={headers}
                useValue={false}
                onChange={setTarget}
              />
            </>
          ) : (
            <>
              <AccountSideEditor
                title="Statement owner"
                side={owner}
                headers={headers}
                useValue={true}
                onChange={setOwner}
              />
              <AccountSideEditor
                title="Counterparty"
                side={counterparty}
                headers={headers}
                useValue={false}
                onChange={setCounterparty}
              />
            </>
          )}
        </div>

        <div className="flex flex-col gap-3 rounded-md border p-3">
          <p className="text-sm font-medium">Transaction fields</p>
          <div className="grid gap-2 grid-cols-2 md:grid-cols-4">
            <ColumnSelect
              label="Reference / ID"
              value={columns.transaction_id}
              headers={headers}
              onChange={setColumn('transaction_id')}
            />
            <ColumnSelect
              label="Date"
              value={columns.date}
              headers={headers}
              onChange={setColumn('date')}
            />
            <ColumnSelect
              label={mode === 'ledger' ? 'Amount' : 'Amount (signed)'}
              value={columns.amount}
              headers={headers}
              onChange={setColumn('amount')}
            />
            {mode === 'statement' && (
              <>
                <ColumnSelect
                  label="Debit (money out)"
                  value={columns.debit}
                  headers={headers}
                  onChange={setColumn('debit')}
                />
                <ColumnSelect
                  label="Credit (money in)"
                  value={columns.credit}
                  headers={headers}
                  onChange={setColumn('credit')}
                />
                <ColumnSelect
                  label="Direction (debit/credit…)"
                  value={columns.direction}
                  headers={headers}
                  onChange={setColumn('direction')}
                />
              </>
            )}
            <ColumnSelect
              label="Currency column"
              value={columns.currency}
              headers={headers}
              onChange={setColumn('currency')}
            />
            <TextField
              label="Currency (fixed)"
              value={currency}
              placeholder="XOF, EUR, ETH…"
              onChange={setCurrency}
            />
            <ColumnSelect
              label="Fees"
              value={columns.fees}
              headers={headers}
              onChange={setColumn('fees')}
            />
            <ColumnSelect
              label="Status"
              value={columns.status}
              headers={headers}
              onChange={setColumn('status')}
            />
            <ColumnSelect
              label="Description"
              value={columns.description}
              headers={headers}
              onChange={setColumn('description')}
            />
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs text-muted-foreground">Channel</Label>
              <Select
                value={effectiveChannel ?? NONE}
                onValueChange={(v) => setChannel(v === NONE ? '' : v)}
              >
                <SelectTrigger className="h-8 w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>— none —</SelectItem>
                  {CHANNELS.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c.replace('_', ' ')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs text-muted-foreground">Decimal separator</Label>
              <Select value={decimalSeparator} onValueChange={setDecimalSeparator}>
                <SelectTrigger className="h-8 w-[140px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>Auto</SelectItem>
                  <SelectItem value=",">Comma (1 500,50)</SelectItem>
                  <SelectItem value=".">Dot (1,500.50)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2 h-8">
              <Switch id="day-first" checked={dayFirst} onCheckedChange={setDayFirst} />
              <Label htmlFor="day-first" className="text-xs">
                Dates are day first (31/01/2024)
              </Label>
            </div>
          </div>
        </div>

        {preview && (
          <div className="flex flex-col gap-3 rounded-md border p-3">
            <div className="flex items-center gap-2">
              {preview.errors.length === 0 ? (
                <CheckCircle2 className="h-4 w-4 text-green-600" />
              ) : (
                <XCircle className="h-4 w-4 text-amber-600" />
              )}
              <p className="text-sm font-medium">
                {preview.valid_rows} of {preview.total_rows} rows are valid
              </p>
              {!previewIsCurrent && <Badge variant="outline">Mapping changed — check again</Badge>}
            </div>
            {preview.errors.length > 0 && (
              <ul className="text-xs text-muted-foreground max-h-32 overflow-auto">
                {preview.errors.map((e) => (
                  <li key={e.row}>
                    Line {e.row}: {e.message}
                  </li>
                ))}
              </ul>
            )}
            {preview.sample.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="px-2 py-1.5 text-left font-medium">Date</th>
                      <th className="px-2 py-1.5 text-left font-medium">From</th>
                      <th className="px-2 py-1.5 text-left font-medium">To</th>
                      <th className="px-2 py-1.5 text-right font-medium">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.sample.slice(0, 10).map((tx) => (
                      <tr key={tx.transaction_id} className="border-t">
                        <td className="px-2 py-1 whitespace-nowrap">
                          {tx.timestamp ? new Date(tx.timestamp).toLocaleString() : '—'}
                        </td>
                        <td className="px-2 py-1 whitespace-nowrap">{tx.source}</td>
                        <td className="px-2 py-1 whitespace-nowrap">{tx.target}</td>
                        <td className="px-2 py-1 whitespace-nowrap text-right">
                          {tx.amount.toLocaleString()} {tx.currency ?? ''}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex justify-end gap-2 shrink-0 pt-2 border-t">
        <Button variant="outline" onClick={onCancel} disabled={isImporting}>
          Cancel
        </Button>
        <Button variant="outline" onClick={handleCheck} disabled={isChecking || isImporting}>
          {isChecking && <Loader2 className="h-4 w-4 animate-spin" />}
          Check
        </Button>
        <Button onClick={handleImport} disabled={!canImport}>
          {isImporting && <Loader2 className="h-4 w-4 animate-spin" />}
          Import {previewIsCurrent ? `${preview?.valid_rows} transactions` : ''}
        </Button>
      </div>
    </div>
  )
}
