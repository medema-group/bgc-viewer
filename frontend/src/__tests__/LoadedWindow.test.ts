import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import LoadedWindow from '@/components/LoadedWindow.vue'
import type { LoadedRecord, LoadedRegion } from '@/composables/useLoadedRecords'
import type { DataProvider } from '@/services/dataProviders/types'

const loadedRecord: LoadedRecord = {
  key: 'mibig/BGC.json:BGC0000001',
  source: 'mibig',
  sourceLabel: 'MIBiG',
  entryId: 'BGC.json:BGC0000001',
  recordId: 'BGC0000001',
  filename: 'BGC.json',
  description: 'An entry',
  regionCount: 1,
  featureCount: 12,
  regions: [{ id: 'region_1', region_number: 1, product: ['NRPS'], start: 0, end: 30000 }],
  provider: {} as DataProvider
}

const loadedRegion: LoadedRegion = {
  key: `${loadedRecord.key}#region_1`,
  record: loadedRecord,
  regionId: 'region_1',
  regionNumber: 1,
  length: 30000,
  product: ['NRPS']
}

const mountWindow = (props: Record<string, unknown> = {}) =>
  mount(LoadedWindow, { props: { records: [loadedRecord], regions: [loadedRegion], ...props } })

describe('LoadedWindow', () => {
  it('lists the loaded regions, which open in the viewer', async () => {
    const wrapper = mountWindow()

    expect(wrapper.findAll('thead th').map(th => th.text()).slice(0, 3)).toEqual(['Record', 'Region', 'Length (kb)'])
    expect(wrapper.get('tbody tr').findAll('td').map(td => td.text()).slice(0, 4)).toEqual([
      'BGC0000001',
      '1',
      '30.0',
      'NRPS'
    ])
    await wrapper.get('tbody tr').trigger('click')
    expect(wrapper.emitted('select-region')).toEqual([[loadedRegion]])
  })

  it('lists records at the record level, with their sources to remove', async () => {
    const wrapper = mountWindow({ level: 'record' })

    expect(wrapper.findAll('thead th').map(th => th.text()).slice(0, 2)).toEqual(['Record', 'Source'])
    await wrapper.get('tbody tr').trigger('click')
    await wrapper.get('[aria-label="Remove MIBiG records"]').trigger('click')

    expect(wrapper.emitted('select')).toEqual([[loadedRecord]])
    expect(wrapper.emitted('remove-source')).toEqual([['mibig']])
  })

  it('offers regions and records, as only the index holds protoclusters', async () => {
    const wrapper = mountWindow()
    const buttons = wrapper.findAll('.level-toggle button')

    expect(buttons.map(button => button.text())).toEqual(['Regions', 'Records'])
    await buttons[1].trigger('click')
    expect(wrapper.emitted('update:level')).toEqual([['record']])
  })

  it('opens the load dialog from its header', async () => {
    const wrapper = mountWindow()
    await wrapper.findAll('button').find(button => button.text() === 'Load data...')!.trigger('click')
    expect(wrapper.emitted('load')).toHaveLength(1)
  })

  it('shows the sources and counts when compact', async () => {
    const wrapper = mountWindow({ compact: true, viewing: true })

    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.get('.compact-label').text()).toBe('Loaded data')
    expect(wrapper.get('.compact-summary').text()).toBe('MIBiG')
    expect(wrapper.get('.compact-count').text()).toBe('1 record · 1 region')
    expect(wrapper.find('.viewing-mark').exists()).toBe(true)

    await wrapper.get('button.compact-card').trigger('click')
    expect(wrapper.emitted('expand')).toHaveLength(1)
    // Loaded data is removed by source, in the window or the load dialog
    expect(wrapper.find('.delete').exists()).toBe(false)
  })
})
