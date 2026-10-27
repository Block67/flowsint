import { create } from 'zustand'
import { transactionAnalyticsService } from '@/api/transaction-analytics-service'
import type {
  TraceDirection,
  TransactionAlert,
  TransactionDetectionParams,
  TransactionTraceResult
} from '@/types'

type PanelMode = 'alerts' | 'trace'

type TransactionAnalysisStore = {
  mode: PanelMode | null
  isLoading: boolean
  error: string | null
  alerts: TransactionAlert[] | null
  params: TransactionDetectionParams
  trace: TransactionTraceResult | null
  traceNodeId: string | null
  traceDirection: TraceDirection
  traceMaxHops: number
  setParams: (params: TransactionDetectionParams) => void
  runDetection: (sketchId: string) => Promise<TransactionAlert[] | null>
  runTrace: (
    sketchId: string,
    nodeId: string,
    direction?: TraceDirection,
    maxHops?: number
  ) => Promise<TransactionTraceResult | null>
  close: () => void
}

export const useTransactionAnalysisStore = create<TransactionAnalysisStore>()((set, get) => ({
  mode: null,
  isLoading: false,
  error: null,
  alerts: null,
  params: {},
  trace: null,
  traceNodeId: null,
  traceDirection: 'downstream',
  traceMaxHops: 4,
  setParams: (params) => set({ params }),
  runDetection: async (sketchId) => {
    set({ mode: 'alerts', isLoading: true, error: null })
    try {
      const alerts = await transactionAnalyticsService.detect(sketchId, get().params)
      set({ alerts, isLoading: false })
      return alerts
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
      return null
    }
  },
  runTrace: async (sketchId, nodeId, direction, maxHops) => {
    const dir = direction ?? get().traceDirection
    const hops = maxHops ?? get().traceMaxHops
    set({
      mode: 'trace',
      isLoading: true,
      error: null,
      traceNodeId: nodeId,
      traceDirection: dir,
      traceMaxHops: hops
    })
    try {
      const trace = await transactionAnalyticsService.trace(sketchId, nodeId, dir, hops)
      set({ trace, isLoading: false })
      return trace
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
      return null
    }
  },
  close: () => set({ mode: null, error: null })
}))
