import { describe, expect, it, vi } from 'vitest'

import { PAGE_SIZE, useAdvancedSearch } from '@/composables/useAdvancedSearch'
import type { BGCViewerAPIProvider } from '@/services/dataProviders/BGCViewerAPIProvider'
import type { SearchFieldInfo, SearchSchema } from '@/services/dataProviders/types'
import { RAW_QUERY_FIELD, conditionRow, createCondition } from '@/services/filterRows'

const field = (name: string, kind: SearchFieldInfo['kind'], extra: Partial<SearchFieldInfo> = {}): SearchFieldInfo => ({
  name,
  kind,
  label: name,
  group: 'General',
  multi: false,
  default_search: false,
  description: '',
  operators: ['contains'],
  facet: false,
  sortable: false,
  ...extra
})

const schema: SearchSchema = {
  fields: [
    field('text', 'full_text'),
    field('product', 'exact', { facet: true, multi: true }),
    field('organism', 'exact', { facet: true, sortable: true })
  ],
  examples: [],
  query_syntax_url: 'https://example.test',
  raw_query_field: RAW_QUERY_FIELD
}

const emptyResponse = { hits: [], has_more: false, total_regions: 0, facets: {} }

function fakeProvider() {
  return {
    getSearchSchema: vi.fn().mockResolvedValue(schema),
    search: vi.fn().mockResolvedValue(emptyResponse),
    getFieldValues: vi.fn().mockResolvedValue({ field: 'product', values: [{ value: 'NRPS', count: 3 }] })
  }
}

function setup() {
  const provider = fakeProvider()
  const search = useAdvancedSearch(() => provider as unknown as BGCViewerAPIProvider)
  return { provider, search }
}

const lastSearch = (provider: ReturnType<typeof fakeProvider>) => provider.search.mock.calls.slice(-1)[0]

describe('useAdvancedSearch', () => {
  it('loads the schema once and starts the builder with one condition', async () => {
    const { provider, search } = setup()
    await search.loadSchema()
    await search.loadSchema()

    expect(provider.getSearchSchema).toHaveBeenCalledTimes(1)
    expect(search.state.rows).toHaveLength(1)
    expect(search.builderFields.value.map(f => f.name)).toEqual(['text', RAW_QUERY_FIELD, 'product', 'organism'])
    expect(search.sortableFields.value).toEqual(['organism'])
  })

  it('searches the builder rows as a filter with the refine facets', async () => {
    const { provider, search } = setup()
    await search.loadSchema()
    search.state.rows = [conditionRow(createCondition('product', 'in', ['NRPS']))]

    await search.search()

    const [level, criteria, options] = lastSearch(provider)!
    expect(level).toBe('region')
    expect(criteria.filter.conditions[0]).toMatchObject({ field: 'product', operator: 'in', value: ['NRPS'] })
    expect(options).toEqual({ page: 1, perPage: PAGE_SIZE, sort: null, facets: ['product', 'organism'] })
    expect(search.state.response).toEqual(emptyResponse)
  })

  it('searches the query string in query mode and clears on a blank one', async () => {
    const { provider, search } = setup()
    search.setMode('query')
    search.state.queryText = 'pfam:PF00550'
    await search.search()
    expect(lastSearch(provider)![1]).toEqual({ query: 'pfam:PF00550' })

    search.state.queryText = '  '
    await search.search()
    expect(provider.search).toHaveBeenCalledTimes(1)
    expect(search.state.response).toBeNull()
  })

  it('pages, sorts, and switches level with the searched criteria', async () => {
    const { provider, search } = setup()
    search.setMode('query')
    search.state.queryText = 'NRPS'
    await search.search()
    search.state.queryText = 'edited but not searched'

    await search.goToPage(3)
    expect(lastSearch(provider)!.slice(0, 2)).toEqual(['region', { query: 'NRPS' }])
    expect(lastSearch(provider)![2].page).toBe(3)
    expect(search.state.page).toBe(3)

    await search.setSort({ field: 'organism', order: 'desc' })
    expect(lastSearch(provider)![2]).toMatchObject({ page: 1, sort: { field: 'organism', order: 'desc' } })

    await search.setLevel('record')
    expect(lastSearch(provider)![0]).toBe('record')
    expect(search.state.searchedLevel).toBe('record')
  })

  it('adds a refinement as an AND condition, bracketing ORed rows', async () => {
    const { provider, search } = setup()
    await search.loadSchema()
    search.state.rows = [
      conditionRow(createCondition('product', 'in', ['NRPS'])),
      conditionRow(createCondition('product', 'in', ['T1PKS']), 'OR')
    ]

    await search.addRefinement('organism', 'Streptomyces')

    const filter = lastSearch(provider)![1].filter
    expect(filter.operator).toBe('AND')
    // (NRPS OR T1PKS) AND organism, the condition kept after the bracket in its own group
    expect(filter.groups[0].operator).toBe('OR')
    expect(filter.groups[1].conditions[0]).toMatchObject({ field: 'organism', operator: 'in', value: ['Streptomyces'] })
  })

  it('turns a query string into a builder condition when refining', async () => {
    const { provider, search } = setup()
    await search.loadSchema()
    search.setMode('query')
    search.state.queryText = 'substrates:Leu'

    await search.addRefinement('product', 'NRPS')

    expect(search.state.mode).toBe('builder')
    const conditions = lastSearch(provider)![1].filter.conditions
    expect(conditions.map((c: { field: string }) => c.field)).toEqual([RAW_QUERY_FIELD, 'product'])
  })

  it('reports API errors with their code', async () => {
    const { provider, search } = setup()
    provider.search.mockRejectedValue({
      response: { data: { error: { code: 'unhonourable_filter', message: 'Cannot run this filter' } } }
    })
    await search.search()
    expect(search.state.error).toEqual({ code: 'unhonourable_filter', message: 'Cannot run this filter' })
  })

  it('is unavailable without a backend provider', async () => {
    const search = useAdvancedSearch(() => null)
    await search.loadSchema()
    expect(search.state.schemaError?.message).toMatch(/only available for backend datasets/)
  })

  it('forgets conditions, schema, and results on reset', async () => {
    const { search } = setup()
    await search.loadSchema()
    await search.search()
    search.reset()
    expect(search.state.rows).toEqual([])
    expect(search.state.schema).toBeNull()
    expect(search.state.response).toBeNull()
  })

  it('loads suggested values through the provider', async () => {
    const { provider, search } = setup()
    expect(await search.loadValues('product', 'NR')).toEqual([{ value: 'NRPS', count: 3 }])
    expect(provider.getFieldValues).toHaveBeenCalledWith('product', 'NR')
  })
})
