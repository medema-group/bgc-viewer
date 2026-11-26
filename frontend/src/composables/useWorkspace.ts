// The windows of the main view: any number of search windows, the loaded data
// window, and the one viewer. One of them has the focus and is shown at normal
// size; the others are compact, so they all fit on the screen together.
//
// Given a storage, the search windows are saved in it as they change and come back
// from it on the next visit: their labels, builder rows, and the searches they ran,
// which run again once an index is open. Results are not saved.
import { computed, ref, shallowReactive, shallowRef, watch } from 'vue'
import type { BGCViewerAPIProvider } from '@/services/dataProviders/BGCViewerAPIProvider'
import type { SearchLevel, SearchSchema, SearchSort } from '@/services/dataProviders/types'
import { cloneRows, useAdvancedSearch, type AdvancedSearch } from '@/composables/useAdvancedSearch'
import type { FilterRow } from '@/services/filterRows'

/** Id of the loaded data window. */
export const LOADED_WINDOW = 'loaded'
/** Id of the viewer, which can have the focus like a window. */
export const VIEWER = 'viewer'

export interface SearchWindowState {
  id: string
  label: string
  search: AdvancedSearch
}

/** Where the search windows are saved in the storage. */
export const WORKSPACE_STORAGE_KEY = 'bgc-viewer-searches'

/** A search window as saved. */
export interface SavedSearch {
  id: string
  label: string
  rows: FilterRow[]
  level: SearchLevel
  sort: SearchSort | null
  /** The rows and level of the search that ran, which runs again; null when none did. */
  searchedRows: FilterRow[] | null
  searchedLevel: SearchLevel
}

export interface SavedWorkspace {
  version: 1
  focus: string
  searches: SavedSearch[]
}

const LEVELS: SearchLevel[] = ['protocluster', 'region', 'record']
const levelOr = (level: unknown, fallback: SearchLevel): SearchLevel =>
  (LEVELS.includes(level as SearchLevel) ? level as SearchLevel : fallback)

/** The saved searches that can be restored, or null when the saved value is not a workspace. */
export function parseSavedWorkspace(value: unknown): SavedWorkspace | null {
  const saved = value as Partial<SavedWorkspace> | null
  if (!saved || saved.version !== 1 || !Array.isArray(saved.searches)) return null
  const searches = saved.searches
    .filter(search => search && typeof search.id === 'string' && /^search-\d+$/.test(search.id)
      && typeof search.label === 'string' && Array.isArray(search.rows))
    .map(search => ({
      id: search.id,
      label: search.label,
      rows: search.rows,
      level: levelOr(search.level, 'region'),
      sort: search.sort ?? null,
      searchedRows: Array.isArray(search.searchedRows) ? search.searchedRows : null,
      searchedLevel: levelOr(search.searchedLevel, levelOr(search.level, 'region'))
    }))
  return { version: 1, focus: typeof saved.focus === 'string' ? saved.focus : VIEWER, searches }
}

export interface WorkspaceOptions {
  /** Where the search windows are saved and restored from; not saved without one. */
  storage?: Storage | null
}

export function useWorkspace(getProvider: () => BGCViewerAPIProvider | null, options: WorkspaceOptions = {}) {
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
    const window = createWindow(`search-${counter}`, `Search ${counter}`, init)
    searches.value = [...searches.value, window]
    focus.value = window.id
    const { search } = window
    if (indexOpen) {
      void search.loadSchema().then(() => {
        if (run && search.state.schema) return search.search()
      })
    }
    return window
  }

  function createWindow(id: string, label: string, init: Partial<AdvancedSearch['state']>): SearchWindowState {
    const search = useAdvancedSearch(getProvider, { getSchema })
    Object.assign(search.state, init)
    // Its label can change; its search keeps reactive state of its own
    return shallowReactive({ id, label, search })
  }

  /** The search windows as saved: what they ask and what they searched, without results. */
  function save(): SavedWorkspace {
    return {
      version: 1,
      focus: focus.value,
      searches: searches.value.map(({ id, label, search: { state } }) => ({
        id,
        label,
        rows: state.rows,
        level: state.level,
        sort: state.sort,
        searchedRows: state.searchedRows,
        searchedLevel: state.searchedLevel
      }))
    }
  }

  /**
   * Bring back saved search windows in place of the current ones. Their searches
   * run again when an index opens. Returns whether any window came back.
   */
  function restore(saved: SavedWorkspace) {
    searches.value = saved.searches.map(search => createWindow(search.id, search.label, {
      rows: cloneRows(search.rows),
      level: search.level,
      sort: search.sort,
      searchedRows: search.searchedRows && cloneRows(search.searchedRows),
      searchedLevel: search.searchedLevel
    }))
    // New windows are numbered after the restored ones
    counter = Math.max(0, ...saved.searches.map(search => Number(search.id.slice('search-'.length))))
    focus.value = saved.focus
    return searches.value.length > 0
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

  const { storage } = options
  if (storage) {
    try {
      const saved = parseSavedWorkspace(JSON.parse(storage.getItem(WORKSPACE_STORAGE_KEY) ?? 'null'))
      if (saved) restore(saved)
    } catch (error) {
      console.warn('Failed to restore the saved searches:', error)
    }
    // Only what is saved is read here, so results coming in do not write again
    watch(() => JSON.stringify(save()), value => {
      try {
        storage.setItem(WORKSPACE_STORAGE_KEY, value)
      } catch (error) {
        console.warn('Failed to save the searches:', error)
      }
    })
  }

  return {
    searches,
    focus,
    focusedSearch: computed(() => findSearch(focus.value)),
    findSearch,
    addSearch,
    duplicateSearch,
    removeSearch,
    openIndex,
    save,
    restore
  }
}

export type Workspace = ReturnType<typeof useWorkspace>
