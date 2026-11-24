// Records loaded beside the backend index: uploaded files and entries fetched from
// antiSMASH DB or MIBiG. Each source keeps its own files, so loading from one
// source leaves the records of the others in place.
import { computed, markRaw, ref } from 'vue'
import { GenbankFileProvider, JSONFileProvider, type DataProvider } from '@/services/dataProviders'
import type { Region } from '@/services/dataProviders/types'
import { EXTERNAL_SOURCES } from '@/services/externalSources'

/** The upload source; the other source keys are those of EXTERNAL_SOURCES. */
export const UPLOAD_SOURCE = 'upload'

/** A file as the loaders emit it. */
export interface LoadedFile {
  name: string
  type: string
  file: File
}

export interface LoadedRecord {
  /** Unique across sources, for list keys. */
  key: string
  source: string
  sourceLabel: string
  entryId: string
  recordId: string
  filename: string
  description: string
  regionCount: number
  featureCount: number
  regions: Region[]
  provider: DataProvider
}

/** A region of a loaded record, for the region-level list. */
export interface LoadedRegion {
  /** Unique across sources, for list keys. */
  key: string
  record: LoadedRecord
  regionId: string
  regionNumber: number
  length: number | null
  product: string[]
}

export function sourceLabel(source: string): string {
  if (source === UPLOAD_SOURCE) return 'Uploaded file'
  return (EXTERNAL_SOURCES as Record<string, { name: string }>)[source]?.name ?? source
}

async function providerFor(file: LoadedFile): Promise<DataProvider | null> {
  const provider = file.type === 'json'
    ? new JSONFileProvider()
    : file.type === 'genbank' ? new GenbankFileProvider() : null
  if (!provider) return null
  await provider.loadFromFile(file.file)
  // The parsed records are large and never edited, so Vue need not track them.
  return markRaw(provider)
}

async function recordsOf(source: string, provider: DataProvider): Promise<LoadedRecord[]> {
  const { records } = await provider.searchRecords('', 1, Number.MAX_SAFE_INTEGER)
  return Promise.all(records.map(async record => {
    const entryId = record.entryId ?? record.recordId
    return {
      key: `${source}/${entryId}`,
      source,
      sourceLabel: sourceLabel(source),
      entryId,
      recordId: record.recordId,
      filename: record.filename ?? '',
      description: record.recordInfo?.description ?? '',
      regionCount: record.regionCount ?? 0,
      featureCount: record.featureCount ?? 0,
      regions: (await provider.getRegions(entryId)).regions,
      provider
    }
  }))
}

function regionsOf(record: LoadedRecord): LoadedRegion[] {
  return record.regions.map(region => ({
    key: `${record.key}#${region.id}`,
    record,
    regionId: region.id,
    regionNumber: region.region_number,
    length: region.start == null || region.end == null ? null : region.end - region.start,
    product: region.product
  }))
}

export function useLoadedRecords() {
  const bySource = ref<Record<string, LoadedRecord[]>>({})
  const loading = ref(0)
  const error = ref<string | null>(null)
  // The loaders send their whole file list on every change, so a file seen before
  // keeps its provider: it is not parsed again, and a viewer showing one of its
  // records, which tells loaded records apart by provider, stays open.
  const providers = new WeakMap<File, Promise<DataProvider | null>>()
  // Bumped by every change to a source, so a load that a newer one or a removal
  // overtook while it was parsing leaves the source as that change left it
  const generations = new Map<string, number>()
  const nextGeneration = (source: string) => {
    const generation = (generations.get(source) ?? 0) + 1
    generations.set(source, generation)
    return generation
  }

  function cachedProviderFor(file: LoadedFile): Promise<DataProvider | null> {
    let provider = providers.get(file.file)
    if (!provider) {
      provider = providerFor(file)
      providers.set(file.file, provider)
      // A file that failed to parse is tried again the next time it is sent
      provider.catch(() => providers.delete(file.file))
    }
    return provider
  }

  /** Every loaded record, uploads first, then the external sources in load order. */
  const records = computed(() => {
    const { [UPLOAD_SOURCE]: uploads = [], ...external } = bySource.value
    return [...uploads, ...Object.values(external).flat()]
  })

  /** The regions of every loaded record, in record order. */
  const regions = computed(() => records.value.flatMap(regionsOf))

  /**
   * Replace the files of one source and return its records; none when a newer
   * change to the source came first, as its result is then dropped.
   */
  async function setFiles(source: string, files: LoadedFile[]): Promise<LoadedRecord[]> {
    const generation = nextGeneration(source)
    const current = () => generations.get(source) === generation
    loading.value += 1
    error.value = null
    try {
      const loaded: LoadedRecord[] = []
      for (const file of files) {
        const provider = await cachedProviderFor(file)
        if (provider) loaded.push(...await recordsOf(source, provider))
      }
      if (!current()) return []
      const next = { ...bySource.value }
      if (loaded.length) next[source] = loaded
      else delete next[source]
      bySource.value = next
      return loaded
    } catch (err: any) {
      if (current()) error.value = `Could not read the loaded files: ${err?.message ?? err}`
      return []
    } finally {
      loading.value -= 1
    }
  }

  function removeSource(source: string) {
    nextGeneration(source)
    const { [source]: _removed, ...rest } = bySource.value
    bySource.value = rest
  }

  return {
    records,
    regions,
    loading: computed(() => loading.value > 0),
    error,
    setFiles,
    removeSource
  }
}

export type LoadedRecords = ReturnType<typeof useLoadedRecords>
