// The query builder edits a flat list of rows joined by per-row AND/OR; they
// are converted to the FilterGroup the search API takes at the edges. AND
// binds before OR, as in SQL. Ported from the BGC Atlas query builder
// (lib/filters/rows.ts and components/ui/filter-builder/helpers.ts).
import type {
  FilterCondition,
  FilterGroup,
  FilterOperator,
  FilterValue,
  SearchFieldInfo
} from './dataProviders/types'

export type Join = 'AND' | 'OR'

export type FilterRow =
  | { kind: 'condition'; id: string; join: Join; condition: FilterCondition }
  | { kind: 'group'; id: string; join: Join; rows: FilterRow[] }

/** Pseudo-field of a condition whose value is a query string. */
export const RAW_QUERY_FIELD = '_query'

/** The catch-all field: `contains` on it is the "any field contains" condition. */
export const TEXT_FIELD = 'text'

const newId = () => (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
  ? crypto.randomUUID()
  : Math.random().toString(36).slice(2))

const emptyGroup = (operator: Join = 'AND'): FilterGroup =>
  ({ id: newId(), operator, conditions: [], groups: [] })

export const createCondition = (
  field: string,
  operator: FilterOperator,
  value: FilterValue = ''
): FilterCondition => ({ id: newId(), field, operator, value })

export const conditionRow = (condition: FilterCondition, join: Join = 'AND'): FilterRow =>
  ({ kind: 'condition', id: newId(), join, condition })

export const groupRow = (rows: FilterRow[], join: Join = 'AND'): FilterRow =>
  ({ kind: 'group', id: newId(), join, rows })

/** Split rows at their ORs: each run is ANDed, the runs are ORed. */
export const runsOf = (rows: FilterRow[]): FilterRow[][] => {
  const runs: FilterRow[][] = []
  rows.forEach((row, i) => {
    if (i === 0 || row.join === 'OR') runs.push([])
    runs[runs.length - 1].push(row)
  })
  return runs
}

const isGroup = (item: FilterCondition | FilterGroup): item is FilterGroup => 'groups' in item

// FilterGroup keeps conditions and groups in separate lists, which would move a
// condition written after a bracket above it; in that case every item becomes a group.
const groupOf = (operator: Join, items: Array<FilterCondition | FilterGroup>): FilterGroup => {
  const firstGroup = items.findIndex(isGroup)
  const reorders = firstGroup >= 0 && items.slice(firstGroup).some(item => !isGroup(item))
  if (reorders) {
    return {
      ...emptyGroup(operator),
      groups: items.map(item => (isGroup(item) ? item : { ...emptyGroup(), conditions: [item] }))
    }
  }
  return {
    ...emptyGroup(operator),
    conditions: items.filter((item): item is FilterCondition => !isGroup(item)),
    groups: items.filter(isGroup)
  }
}

const itemOf = (row: FilterRow): FilterCondition | FilterGroup =>
  (row.kind === 'condition' ? row.condition : rowsToGroup(row.rows))

export function rowsToGroup(rows: FilterRow[]): FilterGroup {
  const runs = runsOf(rows)
  if (runs.length <= 1) return groupOf('AND', (runs[0] ?? []).map(itemOf))
  return groupOf('OR', runs.map(run => (run.length === 1 ? itemOf(run[0]) : groupOf('AND', run.map(itemOf)))))
}

// Inverse of rowsToGroup: same-operator nesting is flattened so a tree written by
// rowsToGroup comes back as the rows that wrote it.
export function groupToRows(group: FilterGroup | null | undefined): FilterRow[] {
  if (!group) return []
  const op: Join = group.operator === 'OR' ? 'OR' : 'AND'
  const out: FilterRow[] = []
  const push = (row: FilterRow) => { out.push({ ...row, join: out.length ? row.join : 'AND' }) }

  const alternatives: FilterRow[][] = [
    ...(group.conditions ?? []).map(c => [conditionRow(c)]),
    ...(group.groups ?? []).map(child => childRows(child, op))
  ].filter(rows => rows.length)

  alternatives.forEach(rows => {
    rows.forEach((row, i) => push({ ...row, join: i === 0 ? op : row.join }))
  })
  return out
}

function childRows(child: FilterGroup, parentOp: Join): FilterRow[] {
  const op: Join = child.operator === 'OR' ? 'OR' : 'AND'
  const size = (child.conditions?.length ?? 0) + (child.groups?.length ?? 0)
  // AND inside OR needs no brackets: AND-before-OR already reads it that way.
  if (op === parentOp || size <= 1 || (op === 'AND' && parentOp === 'OR')) return groupToRows(child)
  const inner = groupToRows(child)
  return inner.length ? [groupRow(inner)] : []
}

/** Whether a condition still lacks a value; the search API drops such conditions. */
export const isBlankCondition = (condition: FilterCondition): boolean => {
  if (condition.operator === 'exists' || condition.operator === 'not_exists') return false
  const entries = Array.isArray(condition.value) ? condition.value : [condition.value]
  return !entries.some(entry => entry !== null && entry !== undefined && `${entry}`.trim().length > 0)
}

export const rowsHaveRules = (rows: FilterRow[]): boolean => rows.some(row => (row.kind === 'condition'
  ? !isBlankCondition(row.condition)
  : rowsHaveRules(row.rows)))

export const pruneRows = (rows: FilterRow[]): FilterRow[] => rows.flatMap((row): FilterRow[] => {
  if (row.kind === 'condition') return isBlankCondition(row.condition) ? [] : [row]
  const inner = pruneRows(row.rows)
  return inner.length ? [{ ...row, rows: inner }] : []
})

export type SummaryPart =
  | { kind: 'text'; value: string }
  | { kind: 'op'; value: Join }
  | { kind: 'paren'; value: '(' | ')' }

export interface SummaryLine { joiner: Join | null; parts: SummaryPart[] }

// One line per top-level item while all rows are ANDed; once an OR appears, one
// line per alternative with the brackets AND-before-OR implies.
export function summarizeRows(rows: FilterRow[], describe: (c: FilterCondition) => string): SummaryLine[] {
  const pruned = pruneRows(rows)
  const op = (value: Join): SummaryPart => ({ kind: 'op', value })
  const paren = (value: '(' | ')'): SummaryPart => ({ kind: 'paren', value })

  const itemParts = (row: FilterRow): SummaryPart[] => {
    if (row.kind === 'condition') return [{ kind: 'text', value: describe(row.condition) }]
    const inner = expression(row.rows)
    return pruneRows(row.rows).length > 1 ? [paren('('), ...inner, paren(')')] : inner
  }
  const runParts = (run: FilterRow[], bracket: boolean): SummaryPart[] => {
    const parts = run.flatMap((row, i) => [...(i ? [op('AND')] : []), ...itemParts(row)])
    return bracket && run.length > 1 ? [paren('('), ...parts, paren(')')] : parts
  }
  function expression(list: FilterRow[]): SummaryPart[] {
    const runs = runsOf(list)
    return runs.flatMap((run, i) => [...(i ? [op('OR')] : []), ...runParts(run, runs.length > 1)])
  }

  const runs = runsOf(pruned)
  if (runs.length <= 1) {
    return pruned.map((row, i) => ({ joiner: i ? 'AND' : null, parts: itemParts(row) }))
  }
  return runs.map((run, i) => ({ joiner: i ? 'OR' : null, parts: runParts(run, true) }))
}

// Lowercase on purpose: a row reads as a phrase, "Product · is any of · NRPS".
export const OPERATOR_LABELS: Record<FilterOperator, string> = {
  in: 'is any of',
  not_in: 'is none of',
  equals: 'is',
  not_equals: 'is not',
  contains: 'contains',
  not_contains: 'does not contain',
  starts_with: 'starts with',
  ends_with: 'ends with',
  gt: 'greater than',
  gte: 'at least',
  lt: 'less than',
  lte: 'at most',
  between: 'between',
  exists: 'has a value',
  not_exists: 'has no value',
  matches: 'matches'
}

/** The pseudo-field entry that lets a query string sit among the conditions. */
export const RAW_QUERY_FIELD_INFO: SearchFieldInfo = {
  name: RAW_QUERY_FIELD,
  kind: 'full_text',
  label: 'Query string',
  group: 'General',
  multi: false,
  default_search: false,
  description: 'A query in the search query language, such as pfam:PF00550 AND substrates:Leu.',
  operators: ['matches'],
  facet: false,
  sortable: false
}

/** The operator a new condition on `field` starts with. */
export const defaultOperator = (field: SearchFieldInfo): FilterOperator => {
  if (field.name === RAW_QUERY_FIELD) return 'matches'
  if (field.kind === 'exact') return field.facet ? 'in' : 'equals'
  if (field.kind === 'numeric') return 'gte'
  if (field.kind === 'boolean') return 'equals'
  return 'contains'
}

export const defaultCondition = (field: SearchFieldInfo): FilterCondition =>
  createCondition(field.name, defaultOperator(field), field.kind === 'boolean' ? 'true' : '')

/** Carry a value across an operator change in the shape the new operator takes. */
export const normalizeValue = (value: FilterValue | undefined, operator: FilterOperator): FilterValue => {
  const first = Array.isArray(value) ? value[0] ?? '' : value ?? ''
  if (operator === 'between') {
    return Array.isArray(value) ? [value[0] ?? '', value[1] ?? ''] : [first, '']
  }
  if (operator === 'in' || operator === 'not_in') {
    const values = Array.isArray(value) ? value : [value ?? null]
    return values.filter(v => v !== null && `${v}`.trim() !== '')
  }
  if (operator === 'exists' || operator === 'not_exists') return ''
  return first
}

const formatValue = (value: FilterValue | undefined, operator: FilterOperator): string => {
  if (operator === 'exists' || operator === 'not_exists') return ''
  if (operator === 'between' && Array.isArray(value)) {
    return value.slice(0, 2).map(v => `${v ?? ''}`.trim()).join(' and ')
  }
  if (Array.isArray(value)) return value.filter(v => v !== null && `${v}` !== '').join(', ')
  if (value === 'true') return 'yes'
  if (value === 'false') return 'no'
  return `${value ?? ''}`
}

/** One condition in words, as the summary shows it: "Product is any of NRPS, T1PKS". */
export const describeCondition = (
  condition: FilterCondition,
  fields: Map<string, SearchFieldInfo>
): string => {
  const label = fields.get(condition.field)?.label ?? condition.field
  let operator = condition.operator
  let value = condition.value
  // A range with one bound left open reads as the comparison it is.
  if (operator === 'between' && Array.isArray(value)) {
    const [min, max] = value.map(v => (v === null || `${v}`.trim() === '' ? null : v))
    if (min === null && max !== null) [operator, value] = ['lte', max ?? '']
    else if (max === null && min !== null) [operator, value] = ['gte', min ?? '']
  }
  const words = OPERATOR_LABELS[operator] ?? operator
  return [label, words, formatValue(value, operator)].filter(Boolean).join(' ')
}
