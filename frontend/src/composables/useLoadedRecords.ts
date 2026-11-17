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

  /** Every loaded record, uploads first, then the external sources in load order. */
  const records = computed(() => {
    const { [UPLOAD_SOURCE]: uploads = [], ...external } = bySource.value
    return [...uploads, ...Object.values(external).flat()]
  })

  /** The regions of every loaded record, in record order. */
  const regions = computed(() => records.value.flatMap(regionsOf))

  /** Replace the files of one source and return its records. */
  async function setFiles(source: string, files: LoadedFile[]): Promise<LoadedRecord[]> {
    loading.value += 1
    error.value = null
    try {
      const loaded: LoadedRecord[] = []
      for (const file of files) {
        const provider = await providerFor(file)
        if (provider) loaded.push(...await recordsOf(source, provider))
      }
      const next = { ...bySource.value }
      if (loaded.length) next[source] = loaded
      else delete next[source]
      bySource.value = next
      return loaded
    } catch (err: any) {
      error.value = `Could not read the loaded files: ${err?.message ?? err}`
      return []
    } finally {
      loading.value -= 1
    }
  }

  function removeSource(source: string) {
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
