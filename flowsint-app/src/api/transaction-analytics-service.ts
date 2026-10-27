import { fetchWithAuth } from './api'
import type {
  TraceDirection,
  TransactionAccountSummary,
  TransactionAlert,
  TransactionDetectionParams,
  TransactionTraceResult
} from '@/types'

export const transactionAnalyticsService = {
  detect: async (
    sketchId: string,
    params: TransactionDetectionParams = {},
    detectors?: string[]
  ): Promise<TransactionAlert[]> => {
    return fetchWithAuth(`/api/sketches/${sketchId}/transactions/alerts`, {
      method: 'POST',
      body: JSON.stringify({ params, detectors: detectors ?? null })
    })
  },
  trace: async (
    sketchId: string,
    nodeId: string,
    direction: TraceDirection = 'downstream',
    maxHops = 4
  ): Promise<TransactionTraceResult> => {
    return fetchWithAuth(`/api/sketches/${sketchId}/transactions/trace`, {
      method: 'POST',
      body: JSON.stringify({ node_id: nodeId, direction, max_hops: maxHops })
    })
  },
  accounts: async (sketchId: string, limit = 50): Promise<TransactionAccountSummary[]> => {
    return fetchWithAuth(`/api/sketches/${sketchId}/transactions/accounts?limit=${limit}`)
  }
}
