import { flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import { VIEWER, useWorkspace } from '@/composables/useWorkspace'
import type { BGCViewerAPIProvider } from '@/services/dataProviders/BGCViewerAPIProvider'
import type { SearchSchema } from '@/services/dataProviders/types'
import { RAW_QUERY_FIELD, conditionRow, createCondition } from '@/services/filterRows'

const schema: SearchSchema = {
  fields: [{
    name: 'text',
    kind: 'full_text',
    label: 'Any text',
    group: 'General',
    multi: false,
    default_search: true,
    description: '',
    operators: ['contains'],
    facet: false,
    sortable: false
  }],
  examples: [],
  query_syntax_url: 'https://example.test',
  raw_query_field: RAW_QUERY_FIELD
}

function setup() {
  const provider = {
    getSearchSchema: vi.fn().mockResolvedValue(schema),
    search: vi.fn().mockResolvedValue({ hits: [], has_more: false, total: 3, facets: {} }),
    getFieldValues: vi.fn()
  }
  const workspace = useWorkspace(() => provider as unknown as BGCViewerAPIProvider)
  return { provider, workspace }
}

const coelicolor = () => [conditionRow(createCondition('text', 'contains', 'coelicolor'))]

describe('useWorkspace', () => {
  it('opens a first index in one search window that lists every region', async () => {
    const { provider, workspace } = setup()
    await workspace.openIndex()

    expect(workspace.searches.value.map(window => window.label)).toEqual(['Search 1'])
    expect(workspace.focus.value).toBe('search-1')
    expect(provider.search).toHaveBeenCalledTimes(1)
    expect(provider.search.mock.calls[0][0]).toBe('region')
  })

  it('lists every region in a window made before the index opened', async () => {
    const { provider, workspace } = setup()
    const first = workspace.addSearch()
    // Without an index, the window does not ask for its fields
    expect(provider.getSearchSchema).not.toHaveBeenCalled()

    await workspace.openIndex()
    expect(workspace.searches.value).toEqual([first])
    expect(first.search.state.response?.total).toBe(3)
  })

  it('fetches the schema once for all windows', async () => {
    const { provider, workspace } = setup()
    await workspace.openIndex()
    const second = workspace.addSearch()
    await flushPromises()

    expect(second.search.state.schema).toEqual(schema)
    expect(provider.getSearchSchema).toHaveBeenCalledTimes(1)
    // A new window only searches when asked
    expect(second.search.state.response).toBeNull()
    expect(workspace.focus.value).toBe(second.id)
  })

  it('duplicates a window with its query and runs it', async () => {
    const { provider, workspace } = setup()
    await workspace.openIndex()
    const [first] = workspace.searches.value
    first.search.state.rows = coelicolor()
    first.search.state.level = 'record'

    const copy = workspace.duplicateSearch(first.id)!
    await flushPromises()

    expect(copy.label).toBe('Search 1 (copy)')
    expect(copy.search.state.rows).toEqual(first.search.state.rows)
    expect(copy.search.state.rows).not.toBe(first.search.state.rows)
    expect(provider.search.mock.calls.slice(-1)[0][0]).toBe('record')
    expect(copy.search.state.searchedRows).toEqual(first.search.state.rows)
  })

  it('moves the focus to the window before a closed one, then to the viewer', async () => {
    const { workspace } = setup()
    const first = workspace.addSearch()
    const second = workspace.addSearch()
    const third = workspace.addSearch()

    workspace.focus.value = second.id
    workspace.removeSearch(second.id)
    expect(workspace.focus.value).toBe(first.id)

    workspace.removeSearch(third.id)
    expect(workspace.focus.value).toBe(first.id)

    workspace.removeSearch(first.id)
    expect(workspace.focus.value).toBe(VIEWER)
  })

  it('runs the searched queries again on another index and keeps the others unsearched', async () => {
    const { provider, workspace } = setup()
    await workspace.openIndex()
    const [first] = workspace.searches.value
    first.search.state.rows = coelicolor()
    await first.search.search()
    const draft = workspace.addSearch()
    await flushPromises()
    draft.search.state.rows = coelicolor()
    provider.search.mockClear()

    await workspace.openIndex()

    expect(provider.getSearchSchema).toHaveBeenCalledTimes(2)
    expect(provider.search).toHaveBeenCalledTimes(1)
    expect(provider.search.mock.calls[0][1].filter.conditions[0]).toMatchObject({ value: 'coelicolor' })
    expect(first.search.state.rows).toMatchObject([{ condition: { value: 'coelicolor' } }])
    expect(first.search.state.response).not.toBeNull()
    expect(draft.search.state.response).toBeNull()
    expect(draft.search.state.rows).toHaveLength(1)
  })
})
