import { describe, expect, it, vi } from 'vitest'

import { PAGE_SIZE, useAdvancedSearch } from '@/composables/useAdvancedSearch'
import type { BGCViewerAPIProvider } from '@/services/dataProviders/BGCViewerAPIProvider'
import type { SearchFieldInfo, SearchSchema } from '@/services/dataProviders/types'
import { RAW_QUERY_FIELD, conditionRow, createCondition, groupRow } from '@/services/filterRows'

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

const emptyResponse = { hits: [], has_more: false, total: 0, facets: {} }

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

  it('drops blank rows before grouping, so the search asks what the summary shows', async () => {
    const { provider, search } = setup()
    await search.loadSchema()
    const condition = (value: string) => createCondition('product', 'in', value ? [value] : [])
    // a OR <blank> AND b: the summary reads "a AND b"
    search.state.rows = [
      conditionRow(condition('a')),
      conditionRow(condition(''), 'OR'),
      conditionRow(condition('b'), 'AND'),
      // An empty bracket goes too
      groupRow([conditionRow(condition(''))], 'OR')
    ]

    await search.search()

    const { filter } = lastSearch(provider)![1]
    expect(filter.operator).toBe('AND')
    expect(filter.groups).toEqual([])
    expect(filter.conditions.map((c: { value: string[] }) => c.value)).toEqual([['a'], ['b']])
  })

  it('puts a query string into the builder as its one condition', async () => {
    const { provider, search } = setup()
    await search.loadSchema()

    search.useQueryString('pfam:PF00550')
    await search.search()

    expect(lastSearch(provider)![1].filter.conditions).toMatchObject([
      { field: RAW_QUERY_FIELD, operator: 'matches', value: 'pfam:PF00550' }
    ])
  })

  it('pages, sorts, and switches level with the searched criteria', async () => {
    const { provider, search } = setup()
    search.useQueryString('NRPS')
    await search.search()
    const searched = lastSearch(provider)![1]
    search.useQueryString('edited but not searched')

    await search.goToPage(3)
    expect(lastSearch(provider)!.slice(0, 2)).toEqual(['region', searched])
    expect(lastSearch(provider)![2].page).toBe(3)
    expect(search.state.page).toBe(3)

    await search.setSort({ field: 'organism', order: 'desc' })
    expect(lastSearch(provider)![2]).toMatchObject({ page: 1, sort: { field: 'organism', order: 'desc' } })

    await search.setLevel('record')
    expect(lastSearch(provider)![0]).toBe('record')
    expect(search.state.searchedLevel).toBe('record')

    await search.setLevel('protocluster')
    expect(lastSearch(provider)!.slice(0, 2)).toEqual(['protocluster', searched])
    expect(search.state.searchedLevel).toBe('protocluster')
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

  it('drops blank rows when refining', async () => {
    const { provider, search } = setup()
    await search.loadSchema()

    await search.addRefinement('product', 'NRPS')

    const conditions = lastSearch(provider)![1].filter.conditions
    expect(conditions.map((c: { field: string }) => c.field)).toEqual(['product'])
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
    expect(provider.getFieldValues).toHaveBeenCalledWith('product', 'NR', undefined, 'region')
  })

  it('counts suggested values at the chosen level', async () => {
    const { provider, search } = setup()
    await search.setLevel('protocluster')
    await search.loadValues('product', 'NR')
    expect(provider.getFieldValues).toHaveBeenCalledWith('product', 'NR', undefined, 'protocluster')
  })
})
