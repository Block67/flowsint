import { type Profile } from './profile'
import { type Investigation } from './investigation'
import { type GraphNode, type GraphEdge } from './graph'

export interface Sketch {
  id: string
  title: string
  description: string
  status?: string
  priority?: string
  created_at: string
  last_updated_at: string
  owner: Profile
  owner_id: string
  relations?: unknown[]
  individuals?: unknown[]
  investigation?: Investigation
  investigation_id: string
  members?: { profile: Profile }[]
}

// Response shape shared by every sketch-service endpoint that returns a
// graph slice (full sketch graph, or a single node's neighbors).
export interface SketchGraphData {
  nds: GraphNode[]
  rls: GraphEdge[]
}

export interface DetectionResult {
  type: string
  key: string
  fields: Array<{
    name: string
    label: string
    description: string
    required: boolean
    primary: boolean
    value: string | null
  }>
}

// One row of the import-preview mapping table: a detected entity the user
// can include/exclude and relabel before it's persisted as a node.
export interface EntityMapping {
  id: string
  entity_type: string
  include: boolean
  nodeLabel: string
  node_id?: string
  data: Record<string, unknown>
}

export interface PreviewEntity {
  detected_type: string
  node_id?: string | number
  obj: Record<string, unknown> & { nodeLabel: string }
}

export interface PreviewEdge {
  from_id: string
  to_id: string
  from_obj: { label: string }
  to_obj: { label: string }
  label: string
}

export interface ImportAnalysisResult {
  entities: Record<string, { results: PreviewEntity[] }>
  edges: PreviewEdge[]
}

export interface ImportExecutionResult {
  status: string
  nodes_created: number
  errors: string[]
}

export type TransactionAccountType =
  | 'MobileMoneyAccount'
  | 'BankAccount'
  | 'CryptoWallet'
  | 'CreditCard'
  | 'Merchant'

export interface TransactionAccountSide {
  account_type: TransactionAccountType
  column?: string | null
  value?: string | null
  provider_column?: string | null
  provider?: string | null
  holder_column?: string | null
  country?: string | null
}

export type TransactionChannel = 'bank' | 'mobile_money' | 'card' | 'crypto' | 'cash' | 'other'

export interface TransactionMapping {
  mode: 'ledger' | 'statement'
  source?: TransactionAccountSide | null
  target?: TransactionAccountSide | null
  owner?: TransactionAccountSide | null
  counterparty?: TransactionAccountSide | null
  transaction_id_column?: string | null
  date_column?: string | null
  date_format?: string | null
  day_first?: boolean
  amount_column?: string | null
  debit_column?: string | null
  credit_column?: string | null
  direction_column?: string | null
  decimal_separator?: ',' | '.' | null
  currency_column?: string | null
  currency?: string | null
  fees_column?: string | null
  status_column?: string | null
  description_column?: string | null
  channel?: TransactionChannel | null
  country?: string | null
}

export interface TransactionTableAnalysis {
  headers: string[]
  sample_rows: Record<string, string | null>[]
  total_rows: number
  suggested_columns: Record<string, string | null>
  suggested_mode: 'ledger' | 'statement'
}

export interface TransactionRowError {
  row: number
  message: string
}

export interface TransactionPreview {
  total_rows: number
  valid_rows: number
  errors: TransactionRowError[]
  sample: {
    transaction_id: string
    source: string
    source_type: string
    target: string
    target_type: string
    amount: number
    currency: string | null
    timestamp: string | null
    description: string | null
  }[]
}

export interface TransactionImportResult {
  status: string
  transactions_imported: number
  accounts_imported: number
  rows_failed: number
  errors: TransactionRowError[]
}
