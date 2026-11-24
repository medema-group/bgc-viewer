import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import RegionViewer from '@/components/RegionViewer.vue'
import RegionViewerContainer from '@/components/RegionViewerContainer.vue'

const regions = [
  { id: 'region_1', region_number: 1, product: ['NRPS'], start: 0, end: 1000 },
  { id: 'region_2', region_number: 2, product: ['terpene'], start: 2000, end: 3000 }
]

function provider() {
  return {
    getPfamColorMap: vi.fn().mockResolvedValue({}),
    loadEntry: vi.fn().mockResolvedValue({ entryId: 'rec.json:rec', recordId: 'rec', filename: 'rec.json' }),
    getRegions: vi.fn().mockResolvedValue({ regions }),
    getTTACodons: vi.fn().mockResolvedValue({ tta_codons: [] }),
    getResistanceFeatures: vi.fn().mockResolvedValue({ resistance_features: [] }),
    getTFBSHits: vi.fn().mockResolvedValue({ hits: [] }),
    getRecordFeatures: vi.fn().mockResolvedValue({ features: [] })
  }
}

async function mountContainer(initialRegionId = '') {
  const wrapper = shallowMount(RegionViewerContainer, {
    props: {
      dataProvider: provider(),
      recordId: 'rec.json:rec',
      recordData: { entryId: 'rec.json:rec', recordId: 'rec', filename: 'rec.json' },
      initialRegionId
    }
  })
  await flushPromises()
  return wrapper
}

const selectedRegion = (wrapper: Awaited<ReturnType<typeof mountContainer>>) =>
  wrapper.findComponent(RegionViewer).props('selectedRegionId')

describe('RegionViewerContainer region selection', () => {
  it('shows the whole record when no region is asked for', async () => {
    expect(selectedRegion(await mountContainer())).toBe('')
  })

  it('selects the asked-for region, and none when the record lacks it', async () => {
    expect(selectedRegion(await mountContainer('region_2'))).toBe('region_2')
    expect(selectedRegion(await mountContainer('region_9'))).toBe('')
  })

  it('goes back to the whole open record when the region request is cleared', async () => {
    const wrapper = await mountContainer('region_2')

    await wrapper.setProps({ initialRegionId: '' })

    expect(selectedRegion(wrapper)).toBe('')
  })
  it('loads the TFBS hits of the whole record in one request', async () => {
    const wrapper = await mountContainer()

    const { getTFBSHits } = wrapper.props('dataProvider') as ReturnType<typeof provider>
    expect(getTFBSHits.mock.calls).toEqual([['rec.json:rec']])
  })
})
