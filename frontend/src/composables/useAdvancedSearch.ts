// State and actions of the advanced search dialog, kept outside the dialog so a
// search survives closing and reopening it.
import { computed, reactive } from 'vue'
import type { BGCViewerAPIProvider } from '@/services/dataProviders/BGCViewerAPIProvider'
import type {
  FacetBucket,
  RecordSearchHit,
  RegionSearchHit,
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
  rowsHaveRules,
  rowsToGroup,
  runsOf,
  type FilterRow
} from '@/services/filterRows'

export type SearchHit = RegionSearchHit | RecordSearchHit
export type SearchMode = 'builder' | 'query'

export interface SearchError {
  code: string
  message: string
}

/** Fields counted beside every search for the refine panel, when the index can count them. */
export const REFINE_FIELDS = ['product_category', 'product', 'organism', 'knowncluster_top_compound']

export const PAGE_SIZE = 20

const NOT_AVAILABLE = 'Advanced search is only available for backend datasets'

function toSearchError(error: any, fallback: string): SearchError {
  const apiError = error?.response?.data?.error
  return apiError && apiError.code && apiError.message
    ? { code: apiError.code, message: apiError.message }
    : { code: fallback, message: error?.message || 'Search failed' }
}

export function useAdvancedSearch(getProvider: () => BGCViewerAPIProvider | null) {
  const state = reactive({
    mode: 'builder' as SearchMode,
    rows: [] as FilterRow[],
    queryText: '',
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

  const canSearch = computed(() => (state.mode === 'builder'
    ? state.schema !== null
    : state.queryText.trim().length > 0))

  const hasRules = computed(() => rowsHaveRules(state.rows))

  function ensureStarterRow() {
    if (state.rows.length === 0 && builderFields.value.length > 0) {
      state.rows = [conditionRow(defaultCondition(builderFields.value[0]))]
    }
  }

  async function loadSchema() {
    if (state.schema || state.schemaLoading) return
    const request = ++schemaRequest
    state.schemaLoading = true
    state.schemaError = null
    try {
      const provider = getProvider()
      if (!provider) throw new Error(NOT_AVAILABLE)
      const schema = await provider.getSearchSchema()
      if (request === schemaRequest) {
        state.schema = schema
        ensureStarterRow()
      }
    } catch (error) {
      if (request === schemaRequest) state.schemaError = toSearchError(error, 'schema_failed')
    } finally {
      if (request === schemaRequest) state.schemaLoading = false
    }
  }

  async function fetchPage(criteria: SearchCriteria, level: SearchLevel, page: number) {
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
        state.searchedLevel = level
        state.page = page
      }
    } catch (error) {
      if (request === searchRequest) state.error = toSearchError(error, 'search_failed')
    } finally {
      if (request === searchRequest) state.loading = false
    }
  }

  /** Run what the builder or the query string asks, from the first page. */
  async function search() {
    if (state.mode === 'query') {
      if (!state.queryText.trim()) {
        clearResults()
        return
      }
      await fetchPage({ query: state.queryText }, state.level, 1)
    } else {
      // A builder without conditions browses every region.
      await fetchPage({ filter: rowsToGroup(state.rows) }, state.level, 1)
    }
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
    if (state.mode === 'query') {
      const text = state.queryText.trim()
      state.rows = text ? [conditionRow(createCondition(RAW_QUERY_FIELD, 'matches', text))] : []
      state.mode = 'builder'
    }
    const kept = state.rows.filter(row => row.kind === 'group' || rowsHaveRules([row]))
    // A new AND row would bind to the last OR alternative only, so ORed rows are bracketed first.
    const base = runsOf(kept).length > 1 ? [groupRow(kept)] : kept
    state.rows = [...base, conditionRow(createCondition(field, 'in', [value]), 'AND')]
    await search()
  }

  function setMode(mode: SearchMode) {
    state.mode = mode
    if (mode === 'builder') ensureStarterRow()
  }

  function clearResults() {
    searchRequest += 1
    state.response = null
    state.searchedCriteria = null
    state.selectedHit = null
    state.loading = false
    state.error = null
    state.page = 1
  }

  /** Forget the conditions and results, as when another index is selected. */
  function reset() {
    clearResults()
    schemaRequest += 1
    state.schema = null
    state.schemaLoading = false
    state.schemaError = null
    state.rows = []
    state.queryText = ''
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
    setMode,
    addRefinement,
    clearResults,
    reset,
    loadValues: async (field: string, contains: string): Promise<FacetBucket[]> => {
      const provider = getProvider()
      if (!provider) throw new Error(NOT_AVAILABLE)
      return (await provider.getFieldValues(field, contains)).values
    }
  }
}

export type AdvancedSearch = ReturnType<typeof useAdvancedSearch>
