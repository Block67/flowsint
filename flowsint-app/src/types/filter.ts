export type TypeFilter = {
  type: string
  checked: boolean
}

export type RuleOperator = 'is' | 'not' | 'like' | 'startsWith' | 'endsWith'
export type RuleKey = 'label' | 'domain' | 'ip'

export type RuleFilter = {
  id: string
  key: RuleKey
  operator: RuleOperator
  matcher: string
}

export type TransactionFilter = {
  from?: string | null // YYYY-MM-DD
  to?: string | null // YYYY-MM-DD, inclusive
  minAmount?: number | null // compared with the edge weight (USD amount when known)
}

export type Filters = {
  types: TypeFilter[]
  rules: RuleFilter[]
  transactions?: TransactionFilter
}
