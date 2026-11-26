// State and actions of one search window: its query builder rows and the results
// they returned. Kept outside the window, so a search survives the window being
// made compact and normal again.
import { computed, effectScope, reactive, watch } from 'vue'
import type { BGCViewerAPIProvider } from '@/services/dataProviders/BGCViewerAPIProvider'
import type {
  FacetBucket,
  SearchCriteria,
  SearchFieldInfo,
  SearchLevel,
  SearchResponse,
  SearchSchema,
  SearchSort
} from '@/services/dataProviders/types'
import {
  RAW_QUERY_FIELD,
  RAW_QUERY_FIELD_INFO,
  TEXT_FIELD,
  conditionRow,
  createCondition,
  defaultCondition,
  groupRow,
  pruneRows,
  rowsHaveRules,
  rowsToGroup,
  runsOf,
  type FilterRow
} from '@/services/filterRows'
import type { SearchHit } from '@/services/searchNavigation'

export type { SearchHit }

export interface SearchError {
  code: string
  message: string
}

/** Fields counted beside every search for the refine panel, when the index can count them. */
export const REFINE_FIELDS = ['product_category', 'product', 'organism', 'knowncluster_top_compound']

export const PAGE_SIZE = 20

/** How long the builder rows must stay unchanged before they are searched (ms). */
export const AUTO_SEARCH_DELAY = 500

const NOT_AVAILABLE = 'Advanced search is only available for backend datasets'

function toSearchError(error: any, fallback: string): SearchError {
  const apiError = error?.response?.data?.error
  return apiError && apiError.code && apiError.message
    ? { code: apiError.code, message: apiError.message }
    : { code: fallback, message: error?.message || 'Search failed' }
}

export interface AdvancedSearchOptions {
  /**
   * Fetches the index schema; given when several searches share one index, so the
   * schema is fetched once for all of them. Defaults to asking the provider.
   */
  getSchema?: () => Promise<SearchSchema>
  /**
   * Search the builder rows by itself once they stay unchanged this long (ms), when
   * they ask something else than the last search; 0 searches only when asked.
   * Defaults to AUTO_SEARCH_DELAY.
   */
  autoSearchDelay?: number
}

/** A deep copy of builder rows, which share no objects with the rows copied. */
export const cloneRows = (rows: FilterRow[]): FilterRow[] => JSON.parse(JSON.stringify(rows))

/**
 * The filter that rows ask for, as text: rows that ask the same differ only in ids,
 * which the conversion makes anew, and in blank conditions, which it leaves out.
 */
export const queryKey = (rows: FilterRow[]): string =>
  JSON.stringify(rowsToGroup(pruneRows(rows)), (key, value) => (key === 'id' ? undefined : value))

export function useAdvancedSearch(
  getProvider: () => BGCViewerAPIProvider | null,
  options: AdvancedSearchOptions = {}
) {
  const state = reactive({
    rows: [] as FilterRow[],
    /** The rows that asked for the shown response, as they were when the search ran. */
    searchedRows: null as FilterRow[] | null,
    level: 'region' as SearchLevel,
    sort: null as SearchSort | null,
    page: 1,
    response: null as SearchResponse<SearchHit> | null,
    /** The level and criteria of the shown response, used for paging and sorting. */
    searchedLevel: 'region' as SearchLevel,
    searchedCriteria: null as SearchCriteria | null,
    selectedHit: null as SearchHit | null,
    loading: false,
    error: null as SearchError | null,
    schema: null as SearchSchema | null,
    schemaLoading: false,
    schemaError: null as SearchError | null
  })
  let searchRequest = 0
  let schemaRequest = 0
  /** The query of the last search asked for, run or under way. */
  let lastQuery: string | null = null
  let autoSearchTimer: ReturnType<typeof setTimeout> | null = null
  const autoSearchDelay = options.autoSearchDelay ?? AUTO_SEARCH_DELAY

  /** Fields offered by the builder: the schema's, with the query-string pseudo-field after "Any text". */
  const builderFields = computed<SearchFieldInfo[]>(() => {
    const fields = state.schema?.fields ?? []
    const at = fields.findIndex(field => field.name === TEXT_FIELD)
    return [...fields.slice(0, at + 1), RAW_QUERY_FIELD_INFO, ...fields.slice(at + 1)]
  })

  const fieldLabels = computed(() => new Map(builderFields.value.map(field => [field.name, field.label])))

  const sortableFields = computed(() => (state.schema?.fields ?? []).filter(f => f.sortable).map(f => f.name))

  const refineFields = computed(() => {
    const countable = new Set((state.schema?.fields ?? []).filter(f => f.facet).map(f => f.name))
    return REFINE_FIELDS.filter(name => countable.has(name))
  })

  const canSearch = computed(() => state.schema !== null)

  const hasRules = computed(() => rowsHaveRules(state.rows))

  function ensureStarterRow() {
    if (state.rows.length === 0 && builderFields.value.length > 0) {
      state.rows = [conditionRow(defaultCondition(builderFields.value[0]))]
    }
  }

  function fetchSchema(): Promise<SearchSchema> {
    if (options.getSchema) return options.getSchema()
    const provider = getProvider()
    if (!provider) throw new Error(NOT_AVAILABLE)
    return provider.getSearchSchema()
  }

  async function loadSchema() {
    if (state.schema || state.schemaLoading) return
    const request = ++schemaRequest
    state.schemaLoading = true
    state.schemaError = null
    try {
      const schema = await fetchSchema()
      if (request === schemaRequest) {
        state.schema = schema
        ensureStarterRow()
        // Rows set before the fields were known have not been searched yet
        scheduleSearch()
      }
    } catch (error) {
      if (request === schemaRequest) state.schemaError = toSearchError(error, 'schema_failed')
    } finally {
      if (request === schemaRequest) state.schemaLoading = false
    }
  }

  async function fetchPage(
    criteria: SearchCriteria,
    level: SearchLevel,
    page: number,
    rows: FilterRow[] | null = state.searchedRows
  ) {
    const request = ++searchRequest
    state.loading = true
    state.error = null
    try {
      const provider = getProvider()
      if (!provider) throw new Error(NOT_AVAILABLE)
      const response = await provider.search(level, criteria, {
        page,
        perPage: PAGE_SIZE,
        sort: state.sort,
        facets: refineFields.value
      })
      if (request === searchRequest) {
        if (page === 1) state.selectedHit = null
        state.response = response
        state.searchedCriteria = criteria
        state.searchedRows = rows
        state.searchedLevel = level
        state.page = page
      }
    } catch (error) {
      if (request === searchRequest) state.error = toSearchError(error, 'search_failed')
    } finally {
      if (request === searchRequest) state.loading = false
    }
  }

  /** Run what the builder rows ask, from the first page. */
  async function search() {
    // A builder without conditions browses every region. Blank rows go before the
    // AND/OR grouping, as in the summary: left in, "a OR <blank> AND b" would group
    // as "a OR (b)" once the backend drops the blank, not as the "a AND b" shown.
    await runRows(state.rows, state.level)
  }

  async function runRows(rows: FilterRow[], level: SearchLevel) {
    cancelScheduledSearch()
    lastQuery = queryKey(rows)
    const pruned = pruneRows(rows)
    await fetchPage({ filter: rowsToGroup(pruned) }, level, 1, cloneRows(pruned))
  }

  /** Search the rows after a pause in editing them, unless they ask what was searched last. */
  function scheduleSearch() {
    cancelScheduledSearch()
    if (autoSearchDelay <= 0) return
    autoSearchTimer = setTimeout(() => {
      autoSearchTimer = null
      void searchNow()
    }, autoSearchDelay)
  }

  function cancelScheduledSearch() {
    if (autoSearchTimer !== null) clearTimeout(autoSearchTimer)
    autoSearchTimer = null
  }

  // Only a change to what the rows ask schedules a search: picking a field or an
  // operator for a condition that has no value yet does not
  const scope = effectScope()
  scope.run(() => watch(() => queryKey(state.rows), scheduleSearch))

  /** Search the rows now instead of after the pause, unless they ask what was searched last. */
  async function searchNow() {
    cancelScheduledSearch()
    if (state.schema && queryKey(state.rows) !== lastQuery) await search()
  }

  /** Stop searching by itself, as when its window is closed. */
  function dispose() {
    cancelScheduledSearch()
    scope.stop()
  }

  async function goToPage(page: number) {
    if (state.searchedCriteria) await fetchPage(state.searchedCriteria, state.searchedLevel, page)
  }

  async function setSort(sort: SearchSort | null) {
    state.sort = sort
    if (state.searchedCriteria) await fetchPage(state.searchedCriteria, state.searchedLevel, 1)
  }

  async function setLevel(level: SearchLevel) {
    state.level = level
    if (state.searchedCriteria) await fetchPage(state.searchedCriteria, level, 1)
  }

  /** Narrow the search to `field` = `value`, as a refine-panel click asks, and run it. */
  async function addRefinement(field: string, value: string) {
    const kept = state.rows.filter(row => row.kind === 'group' || rowsHaveRules([row]))
    // A new AND row would bind to the last OR alternative only, so ORed rows are bracketed first.
    const base = runsOf(kept).length > 1 ? [groupRow(kept)] : kept
    state.rows = [...base, conditionRow(createCondition(field, 'in', [value]), 'AND')]
    await search()
  }

  /** Replace the rows with one query-string condition, as a help example asks. */
  function useQueryString(query: string) {
    state.rows = [conditionRow(createCondition(RAW_QUERY_FIELD, 'matches', query))]
  }

  function clearResults() {
    searchRequest += 1
    lastQuery = null
    cancelScheduledSearch()
    state.response = null
    state.searchedCriteria = null
    state.searchedRows = null
    state.selectedHit = null
    state.loading = false
    state.error = null
    state.page = 1
  }

  /** Start over on a newly opened index and list its regions. */
  async function openIndex() {
    reset()
    state.level = 'region'
    await loadSchema()
    if (state.schema) await search()
  }

  /**
   * Run the same query on a newly opened index: the builder rows and level are
   * kept, the schema is fetched again, and the search that gave the shown results
   * runs again first; edits made to the rows since are searched after a pause, as
   * any edit is. A search under way runs again as asked.
   */
  async function reopenIndex() {
    const running = state.loading
    const rows = running ? pruneRows(state.rows) : state.searchedRows
    const level = running ? state.level : state.searchedLevel
    clearResults()
    forgetSchema()
    await loadSchema()
    if (state.schema && rows) await runRows(rows, level)
    // Edits made since are searched after it, as they would have been
    scheduleSearch()
  }

  function forgetSchema() {
    schemaRequest += 1
    state.schema = null
    state.schemaLoading = false
    state.schemaError = null
  }

  /** Forget the conditions and results, as when another index is selected. */
  function reset() {
    clearResults()
    forgetSchema()
    state.rows = []
    state.sort = null
  }

  return {
    state,
    builderFields,
    fieldLabels,
    sortableFields,
    canSearch,
    hasRules,
    loadSchema,
    search,
    goToPage,
    setSort,
    setLevel,
    useQueryString,
    addRefinement,
    clearResults,
    reset,
    openIndex,
    reopenIndex,
    searchNow,
    dispose,
    loadValues: async (field: string, contains: string): Promise<FacetBucket[]> => {
      const provider = getProvider()
      if (!provider) throw new Error(NOT_AVAILABLE)
      // Counts follow the level the results are listed at.
      return (await provider.getFieldValues(field, contains, undefined, state.level)).values
    }
  }
}

export type AdvancedSearch = ReturnType<typeof useAdvancedSearch>
