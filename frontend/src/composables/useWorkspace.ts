// The windows of the main view: any number of search windows, the loaded data
// window, and the one viewer. One of them has the focus and is shown at normal
// size; the others are compact, so they all fit on the screen together.
import { computed, ref, shallowReactive, shallowRef } from 'vue'
import type { BGCViewerAPIProvider } from '@/services/dataProviders/BGCViewerAPIProvider'
import type { SearchSchema } from '@/services/dataProviders/types'
import { cloneRows, useAdvancedSearch, type AdvancedSearch } from '@/composables/useAdvancedSearch'

/** Id of the loaded data window. */
export const LOADED_WINDOW = 'loaded'
/** Id of the viewer, which can have the focus like a window. */
export const VIEWER = 'viewer'

export interface SearchWindowState {
  id: string
  label: string
  search: AdvancedSearch
}

export function useWorkspace(getProvider: () => BGCViewerAPIProvider | null) {
  // Shallow, as each search keeps reactive state of its own; the list is replaced on every change
  const searches = shallowRef<SearchWindowState[]>([])
  /** The window shown at normal size, or the viewer. */
  const focus = ref<string>(VIEWER)
  let counter = 0
  /** Whether an index was opened, so a new search can fetch its fields. */
  let indexOpen = false

  // Every search reads the same index, so its schema is fetched once for all of them
  let schema: Promise<SearchSchema> | null = null
  const getSchema = () => {
    if (!schema) {
      const provider = getProvider()
      if (!provider) return Promise.reject(new Error('Advanced search is only available for backend datasets'))
      schema = provider.getSearchSchema()
      // A failed fetch is tried again by the next search that asks
      schema.catch(() => { schema = null })
    }
    return schema
  }

  const findSearch = (id: string) => searches.value.find(window => window.id === id) ?? null

  /**
   * Add a search window with the given rows (one blank condition when none) and
   * focus it. It fetches the fields of the open index, and searches when `run` asks.
   */
  function addSearch(
    init: Partial<Pick<AdvancedSearch['state'], 'rows' | 'level' | 'sort'>> = {},
    { run = false } = {}
  ) {
    counter += 1
    const search = useAdvancedSearch(getProvider, { getSchema })
    Object.assign(search.state, init)
    // Its label can change; its search keeps reactive state of its own
    const window: SearchWindowState = shallowReactive({ id: `search-${counter}`, label: `Search ${counter}`, search })
    searches.value = [...searches.value, window]
    focus.value = window.id
    if (indexOpen) {
      void search.loadSchema().then(() => {
        if (run && search.state.schema) return search.search()
      })
    }
    return window
  }

  /** A new search window asking what another one asks, run straight away. */
  function duplicateSearch(id: string) {
    const source = findSearch(id)
    if (!source) return null
    const { rows, level, sort } = source.search.state
    const copy = addSearch({ rows: cloneRows(rows), level, sort }, { run: true })
    copy.label = `${source.label} (copy)`
    return copy
  }

  /** Close a search window; the focus moves to the window before it, or to the viewer. */
  function removeSearch(id: string) {
    const index = searches.value.findIndex(window => window.id === id)
    if (index < 0) return
    searches.value = searches.value.filter(window => window.id !== id)
    if (focus.value === id) {
      focus.value = searches.value[Math.max(0, index - 1)]?.id ?? VIEWER
    }
  }

  /**
   * Open the searches on a newly opened index. Each window keeps its query and
   * runs it again if it had run. On the first index, a window that asks nothing
   * yet lists every region; without windows, one is added to do so.
   */
  async function openIndex() {
    schema = null
    const firstIndex = !indexOpen
    indexOpen = true
    const added = searches.value.length === 0 ? addSearch() : null
    await Promise.all(searches.value.map(({ search }) =>
      (firstIndex || search === added?.search) && !search.state.searchedRows && !search.hasRules.value
        ? search.openIndex()
        : search.reopenIndex()))
  }

  return {
    searches,
    focus,
    focusedSearch: computed(() => findSearch(focus.value)),
    findSearch,
    addSearch,
    duplicateSearch,
    removeSearch,
    openIndex
  }
}

export type Workspace = ReturnType<typeof useWorkspace>
