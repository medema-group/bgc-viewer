import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import LoadedRecordsList from '@/components/LoadedRecordsList.vue'
import { UPLOAD_SOURCE, useLoadedRecords, type LoadedFile } from '@/composables/useLoadedRecords'

// jsdom's File lacks text(), which browsers have.
const fileWithText = (content: string, name: string): File => {
  const file = new File([content], name, { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: () => Promise.resolve(content), configurable: true, writable: true })
  return file
}

const antismashFile = (name: string, recordIds: string[]): LoadedFile => {
  const data = {
    version: '8.0.0',
    input_file: name.replace('.json', '.gbk'),
    records: recordIds.map(id => ({
      id,
      description: `${id} description`,
      features: [
        { type: 'region', location: '[0:100](+)', qualifiers: { region_number: ['1'], product: ['NRPS'] } },
        { type: 'CDS', location: '[10:50](+)', qualifiers: {} }
      ]
    }))
  }
  return {
    name,
    type: 'json',
    file: fileWithText(JSON.stringify(data), name)
  }
}

describe('useLoadedRecords', () => {
  it('keeps the provider of a file sent again, without parsing it again', async () => {
    const loaded = useLoadedRecords()
    const first = antismashFile('first.json', ['recA'])
    const read = vi.spyOn(first.file, 'text')

    const [before] = await loaded.setFiles(UPLOAD_SOURCE, [first])
    // An upload added: the loader sends the whole list, the earlier file included
    await loaded.setFiles(UPLOAD_SOURCE, [first, antismashFile('second.json', ['recB'])])
    // And removed again
    await loaded.setFiles(UPLOAD_SOURCE, [first])

    expect(loaded.records.value.map(record => record.recordId)).toEqual(['recA'])
    expect(loaded.records.value[0].provider).toBe(before.provider)
    expect(read).toHaveBeenCalledTimes(1)
  })

  it('reads a file that failed to parse again when it is sent again', async () => {
    const loaded = useLoadedRecords()
    const file = antismashFile('broken.json', ['recA'])
    const content = await file.file.text()
    const read = vi.spyOn(file.file, 'text').mockResolvedValueOnce('{ not json')

    expect(await loaded.setFiles(UPLOAD_SOURCE, [file])).toEqual([])
    expect(loaded.error.value).toContain('Could not read the loaded files')

    read.mockResolvedValueOnce(content)
    expect((await loaded.setFiles(UPLOAD_SOURCE, [file])).map(record => record.recordId)).toEqual(['recA'])
  })

  it('lists the records of each source, uploads first', async () => {
    const loaded = useLoadedRecords()

    await loaded.setFiles('mibig', [antismashFile('BGC0000001.1.json', ['BGC0000001'])])
    const uploads = await loaded.setFiles(UPLOAD_SOURCE, [antismashFile('mine.json', ['recA', 'recB'])])

    expect(uploads.map(record => record.recordId)).toEqual(['recA', 'recB'])
    expect(loaded.records.value.map(record => [record.sourceLabel, record.recordId])).toEqual([
      ['Uploaded file', 'recA'],
      ['Uploaded file', 'recB'],
      ['MIBiG', 'BGC0000001']
    ])
    expect(loaded.records.value[0]).toMatchObject({
      entryId: 'mine.json:recA',
      filename: 'mine.json',
      description: 'recA description',
      regionCount: 1,
      featureCount: 2
    })
    expect(loaded.regions.value.map(region => [region.record.recordId, region.regionId, region.length])).toEqual([
      ['recA', 'region_1', 100],
      ['recB', 'region_1', 100],
      ['BGC0000001', 'region_1', 100]
    ])
  })

  it('replaces the files of one source and leaves the others', async () => {
    const loaded = useLoadedRecords()
    await loaded.setFiles(UPLOAD_SOURCE, [antismashFile('mine.json', ['recA'])])
    await loaded.setFiles('mibig', [antismashFile('BGC0000001.1.json', ['BGC0000001'])])

    await loaded.setFiles('mibig', [antismashFile('BGC0000002.1.json', ['BGC0000002'])])
    expect(loaded.records.value.map(record => record.recordId)).toEqual(['recA', 'BGC0000002'])

    await loaded.setFiles(UPLOAD_SOURCE, [])
    loaded.removeSource('mibig')
    expect(loaded.records.value).toEqual([])
  })

  describe('a load overtaken while it parses', () => {
    /** A file whose reading waits until `finish` is called with the content to read. */
    function slowFile(name: string) {
      const file = antismashFile(name, ['recA'])
      const content = file.file.text()
      let finish!: (text?: string) => void
      vi.spyOn(file.file, 'text').mockReturnValueOnce(new Promise<string>(resolve => {
        finish = async (text?: string) => resolve(text ?? await content)
      }))
      return { file, finish: (text?: string) => finish(text) }
    }

    it('does not bring back uploads removed meanwhile', async () => {
      const loaded = useLoadedRecords()
      const slow = slowFile('slow.json')

      const pending = loaded.setFiles(UPLOAD_SOURCE, [slow.file])
      // Every upload removed: the loader sends an empty list
      await loaded.setFiles(UPLOAD_SOURCE, [])
      slow.finish()

      expect(await pending).toEqual([])
      expect(loaded.records.value).toEqual([])
    })

    it('does not bring back a source removed meanwhile', async () => {
      const loaded = useLoadedRecords()
      const slow = slowFile('BGC0000001.1.json')

      const pending = loaded.setFiles('mibig', [slow.file])
      loaded.removeSource('mibig')
      slow.finish()

      expect(await pending).toEqual([])
      expect(loaded.records.value).toEqual([])
    })

    it('neither replaces a newer selection nor reports its own error', async () => {
      const loaded = useLoadedRecords()
      const slow = slowFile('slow.json')

      const pending = loaded.setFiles(UPLOAD_SOURCE, [slow.file])
      await loaded.setFiles(UPLOAD_SOURCE, [antismashFile('newer.json', ['recB'])])
      slow.finish('{ not json')
      await pending

      expect(loaded.records.value.map(record => record.recordId)).toEqual(['recB'])
      expect(loaded.error.value).toBeNull()
      expect(loaded.loading.value).toBe(false)
    })

    it('leaves other sources alone', async () => {
      const loaded = useLoadedRecords()
      const slow = slowFile('mine.json')

      const pending = loaded.setFiles(UPLOAD_SOURCE, [slow.file])
      await loaded.setFiles('mibig', [antismashFile('BGC0000001.1.json', ['BGC0000001'])])
      slow.finish()
      await pending

      expect(loaded.records.value.map(record => record.recordId)).toEqual(['recA', 'BGC0000001'])
    })
  })

  it('reports files it cannot read', async () => {
    const loaded = useLoadedRecords()
    const broken = { name: 'broken.json', type: 'json', file: fileWithText('{', 'broken.json') }

    expect(await loaded.setFiles(UPLOAD_SOURCE, [broken])).toEqual([])
    expect(loaded.error.value).toMatch(/Could not read the loaded files/)
    expect(loaded.loading.value).toBe(false)
  })
})

describe('LoadedRecordsList', () => {
  it('selects records and removes a downloaded source once', async () => {
    const loaded = useLoadedRecords()
    await loaded.setFiles(UPLOAD_SOURCE, [antismashFile('mine.json', ['recA'])])
    await loaded.setFiles('mibig', [antismashFile('BGC.json', ['BGC0000001', 'BGC0000002'])])
    const records = loaded.records.value

    const wrapper = mount(LoadedRecordsList, { props: { records, selectedKey: records[1].key } })

    expect(wrapper.findAll('tbody tr')[1].classes()).toContain('selected')
    expect(wrapper.findAll('tbody tr')[0].findAll('td').map(td => td.text()).slice(0, 4)).toEqual([
      'recA',
      'Uploaded file',
      'mine.json',
      'recA description'
    ])
    // Uploads are removed in the load dialog; a downloaded source has one remove button
    expect(wrapper.findAll('td.remove button')).toHaveLength(1)

    await wrapper.findAll('tbody tr')[2].trigger('click')
    await wrapper.get('[aria-label="Remove MIBiG records"]').trigger('click')

    expect(wrapper.emitted('select')).toEqual([[records[2]]])
    expect(wrapper.emitted('remove-source')).toEqual([['mibig']])
  })

  it('lists regions with their record when asked for the region level', async () => {
    const loaded = useLoadedRecords()
    await loaded.setFiles('mibig', [antismashFile('BGC.json', ['BGC0000001', 'BGC0000002'])])
    const regions = loaded.regions.value

    const wrapper = mount(LoadedRecordsList, {
      props: { records: loaded.records.value, regions, level: 'region', selectedKey: regions[1].key }
    })

    expect(wrapper.findAll('tbody tr')[1].classes()).toContain('selected')
    expect(wrapper.findAll('tbody tr')[0].findAll('td').map(td => td.text()).slice(0, 6)).toEqual([
      'BGC0000001',
      '1',
      '0.1',
      'NRPS',
      'MIBiG',
      'BGC.json'
    ])
    expect(wrapper.findAll('td.remove button')).toHaveLength(1)

    await wrapper.findAll('tbody tr')[1].trigger('click')
    expect(wrapper.emitted('select-region')).toEqual([[regions[1]]])
  })
})
