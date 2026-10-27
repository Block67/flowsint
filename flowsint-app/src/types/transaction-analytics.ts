export type TransactionAlertType = 'fan_out' | 'fan_in' | 'pass_through' | 'structuring' | 'cycle'

export interface TransactionAlert {
  type: TransactionAlertType
  title: string
  score: number
  node_ids: string[]
  edge_ids: string[]
  details: Record<string, unknown>
}

export interface TransactionDetectionParams {
  fan_window_hours?: number
  fan_min_counterparties?: number
  pass_through_window_hours?: number
  pass_through_ratio?: number
  pass_through_min_amount?: number
  pass_through_min_events?: number
  pass_through_min_share?: number
  structuring_threshold?: number | null
  structuring_currency?: string | null
  structuring_margin?: number
  structuring_window_hours?: number
  structuring_min_count?: number
  cycle_min_length?: number
  cycle_max_length?: number
  cycle_window_hours?: number | null
  max_cycles?: number
}

export type TraceDirection = 'downstream' | 'upstream'

export interface TransactionTraceResult {
  start_node_id: string
  direction: TraceDirection
  nodes: Record<string, { hops: number; first_seen: number | null; label: string | null }>
  edge_ids: string[]
}

export interface TransactionAccountSummary {
  node_id: string
  label: string | null
  currency: string | null
  inflow: number
  outflow: number
  net: number
  tx_in: number
  tx_out: number
  senders: number
  receivers: number
  first_seen: number | null
  last_seen: number | null
}
