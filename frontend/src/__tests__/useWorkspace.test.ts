import { flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import { VIEWER, WORKSPACE_STORAGE_KEY, useWorkspace } from '@/composables/useWorkspace'
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

function memoryStorage(initial: Record<string, string> = {}) {
  const items = new Map(Object.entries(initial))
  return {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => { items.set(key, value) },
    saved: () => JSON.parse(items.get(WORKSPACE_STORAGE_KEY) ?? 'null')
  }
}

function setup(storage?: ReturnType<typeof memoryStorage>) {
  const provider = {
    getSearchSchema: vi.fn().mockResolvedValue(schema),
    search: vi.fn().mockResolvedValue({ hits: [], has_more: false, total: 3, facets: {} }),
    getFieldValues: vi.fn()
  }
  const workspace = useWorkspace(() => provider as unknown as BGCViewerAPIProvider, {
    storage: storage as unknown as Storage
  })
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

  describe('saving in the browser', () => {
    it('saves the windows as they change, with what they searched but not the results', async () => {
      const storage = memoryStorage()
      const { workspace } = setup(storage)
      await workspace.openIndex()
      const [first] = workspace.searches.value
      first.label = 'Coelicolor'
      first.search.state.rows = coelicolor()
      await first.search.search()
      first.search.state.level = 'record'
      await flushPromises()

      const saved = storage.saved()
      expect(saved).toMatchObject({
        version: 1,
        focus: first.id,
        searches: [{
          id: first.id,
          label: 'Coelicolor',
          level: 'record',
          searchedLevel: 'region',
          rows: [{ condition: { value: 'coelicolor' } }],
          searchedRows: [{ condition: { value: 'coelicolor' } }]
        }]
      })
      expect(JSON.stringify(saved)).not.toContain('"total"')

      workspace.removeSearch(first.id)
      await flushPromises()
      expect(storage.saved().searches).toEqual([])
    })

    it('brings the windows back and runs what they searched once the index opens', async () => {
      const storage = memoryStorage()
      const before = setup(storage).workspace
      await before.openIndex()
      const [first] = before.searches.value
      first.search.state.rows = coelicolor()
      first.search.state.level = 'record'
      await first.search.search()
      // Edited after the search, and not searched again
      first.search.state.rows = [...coelicolor(), ...coelicolor()]
      const second = before.addSearch()
      second.label = 'Draft'
      second.search.state.rows = coelicolor()
      before.focus.value = first.id
      await flushPromises()

      const { provider, workspace } = setup(memoryStorage({ [WORKSPACE_STORAGE_KEY]: JSON.stringify(storage.saved()) }))
      expect(workspace.searches.value.map(window => [window.id, window.label])).toEqual([
        ['search-1', 'Search 1'],
        ['search-2', 'Draft']
      ])
      expect(workspace.focus.value).toBe('search-1')
      const [restored, draft] = workspace.searches.value
      expect(restored.search.state.rows).toHaveLength(2)
      expect(provider.search).not.toHaveBeenCalled()

      await workspace.openIndex()

      // Only the search that ran before runs again, as it was searched
      expect(provider.search).toHaveBeenCalledTimes(1)
      const [level, criteria] = provider.search.mock.calls[0]
      expect(level).toBe('record')
      expect(criteria.filter.conditions).toHaveLength(1)
      expect(restored.search.state.response).not.toBeNull()
      expect(restored.search.state.rows).toHaveLength(2)
      expect(draft.search.state.response).toBeNull()
      expect(draft.search.state.rows).toMatchObject([{ condition: { value: 'coelicolor' } }])

      // New windows are numbered after the restored ones
      expect(workspace.addSearch().label).toBe('Search 3')
    })

    it('starts without windows when the saved value cannot be used', () => {
      for (const value of ['not json', '{"version":2,"searches":[]}', '{"version":1,"searches":[{"id":"x"}]}']) {
        const { workspace } = setup(memoryStorage({ [WORKSPACE_STORAGE_KEY]: value }))
        expect(workspace.searches.value).toEqual([])
      }
    })
  })
})
