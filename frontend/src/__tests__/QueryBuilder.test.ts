import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ConditionRow from '@/components/ConditionRow.vue'
import QueryBuilder from '@/components/QueryBuilder.vue'
import ValueCombobox from '@/components/ValueCombobox.vue'
import type { FilterCondition, SearchFieldInfo } from '@/services/dataProviders/types'
import { RAW_QUERY_FIELD_INFO, conditionRow, createCondition, type FilterRow } from '@/services/filterRows'

const field = (
  name: string,
  kind: SearchFieldInfo['kind'],
  group: string,
  operators: SearchFieldInfo['operators'],
  facet = false
): SearchFieldInfo => ({
  name,
  kind,
  label: name.toUpperCase(),
  group,
  multi: false,
  default_search: false,
  description: '',
  operators,
  facet,
  sortable: false
})

const fields: SearchFieldInfo[] = [
  field('text', 'full_text', 'General', ['contains', 'not_contains']),
  RAW_QUERY_FIELD_INFO,
  field('product', 'exact', 'Region', ['in', 'not_in', 'equals', 'contains', 'exists'], true),
  field('length', 'numeric', 'Region', ['gte', 'between']),
  field('is_complete', 'boolean', 'Region', ['equals', 'not_equals'])
]

const loadValues = vi.fn().mockResolvedValue([{ value: 'NRPS', count: 4 }, { value: 'T1PKS', count: 2 }])

function mountRow(condition: FilterCondition) {
  return mount(ConditionRow, { props: { condition, fields, loadValues } })
}

const lastUpdate = (wrapper: ReturnType<typeof mountRow>) =>
  wrapper.emitted<[FilterCondition]>('update')!.slice(-1)[0]![0]

describe('ConditionRow', () => {
  it('lists the groups and the fields of the selected group', () => {
    const wrapper = mountRow(createCondition('product', 'in', []))
    const options = (label: string) => wrapper.get(`[aria-label="${label}"]`).findAll('option').map(o => o.text())

    expect(options('Field group')).toEqual(['General', 'Region'])
    expect(options('Field')).toEqual(['PRODUCT', 'LENGTH', 'IS_COMPLETE'])
    expect(options('Operator')).toEqual(['is any of', 'is none of', 'is', 'contains', 'has a value'])
  })

  it('resets operator and value when the field changes', async () => {
    const wrapper = mountRow(createCondition('product', 'in', ['NRPS']))
    await wrapper.get('[aria-label="Field"]').setValue('length')
    expect(lastUpdate(wrapper)).toMatchObject({ field: 'length', operator: 'gte', value: '' })

    await wrapper.get('[aria-label="Field group"]').setValue('General')
    expect(lastUpdate(wrapper)).toMatchObject({ field: 'text', operator: 'contains' })
  })

  it('keeps the value in the new operator shape', async () => {
    const wrapper = mountRow(createCondition('length', 'gte', '100'))
    await wrapper.get('[aria-label="Operator"]').setValue('between')
    expect(lastUpdate(wrapper)).toMatchObject({ operator: 'between', value: ['100', ''] })
  })

  it('keeps an operator the field does not offer visible', () => {
    const wrapper = mountRow(createCondition('length', 'contains', '1'))
    const options = wrapper.get('[aria-label="Operator"]').findAll('option').map(o => o.text())
    expect(options).toContain('contains')
  })

  it.each([
    [createCondition('product', 'in', []), ValueCombobox],
    [createCondition('product', 'exists'), null]
  ])('picks the value input for %o', (condition, component) => {
    const wrapper = mountRow(condition)
    expect(wrapper.findComponent(ValueCombobox).exists()).toBe(component !== null)
    if (!component) expect(wrapper.find('[aria-label="Value"]').exists()).toBe(false)
  })

  it('edits a range', async () => {
    const wrapper = mountRow(createCondition('length', 'between', ['', '']))
    await wrapper.get('[aria-label="Minimum"]').setValue('5')
    expect(lastUpdate(wrapper).value).toEqual(['5', ''])
  })

  it('edits yes/no values and query strings', async () => {
    const yesNo = mountRow(createCondition('is_complete', 'equals', 'true'))
    await yesNo.get('[aria-label="Value"]').setValue('false')
    expect(lastUpdate(yesNo).value).toBe('false')

    const raw = mountRow(createCondition('_query', 'matches', ''))
    expect(raw.get('[aria-label="Value"]').classes()).toContain('query-input')
    await raw.get('[aria-label="Value"]').setValue('pfam:PF00550')
    expect(lastUpdate(raw).value).toBe('pfam:PF00550')
  })

  it('asks to be removed', async () => {
    const wrapper = mountRow(createCondition('text', 'contains', 'x'))
    await wrapper.get('[aria-label="Remove condition"]').trigger('click')
    expect(wrapper.emitted('remove')).toHaveLength(1)
  })
})

describe('ValueCombobox', () => {
  function mountCombobox(modelValue: string[], multiple: boolean) {
    return mount(ValueCombobox, {
      props: { field: 'product', fieldLabel: 'Product', modelValue, multiple, loadValues },
      attachTo: document.body
    })
  }

  it('loads values with counts when opened and picks one', async () => {
    const wrapper = mountCombobox([], false)
    await wrapper.get('[role="combobox"]').trigger('click')
    // Past the 200 ms typing debounce. Real time, as Vue ignores events older
    // than a handler attached on a fake clock.
    await new Promise(resolve => setTimeout(resolve, 250))
    await flushPromises()

    expect(loadValues).toHaveBeenCalledWith('product', '')
    expect(wrapper.findAll('[role="option"]').map(o => o.text())).toEqual(['NRPS4', 'T1PKS2'])
    await wrapper.findAll('[role="option"]')[1].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[['T1PKS']]])
    expect(wrapper.find('.combobox-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it('toggles values and shows chips when multiple', async () => {
    const wrapper = mountCombobox(['NRPS'], true)
    expect(wrapper.get('.chips').text()).toContain('NRPS')
    await wrapper.get('[aria-label="Remove NRPS"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[[]]])
    wrapper.unmount()
  })

  it('takes typed text on Enter', async () => {
    const wrapper = mountCombobox([], true)
    await wrapper.get('[role="combobox"]').trigger('click')
    const search = wrapper.get('[aria-label="Search Product values"]')
    await search.setValue('lanthipeptide')
    await search.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')).toEqual([[['lanthipeptide']]])
    wrapper.unmount()
  })
})

describe('QueryBuilder', () => {
  function mountBuilder(rows: FilterRow[]) {
    return mount(QueryBuilder, { props: { rows, fields, loadValues } })
  }

  const lastRows = (wrapper: ReturnType<typeof mountBuilder>) =>
    wrapper.emitted<[FilterRow[]]>('update:rows')!.slice(-1)[0]![0]

  it('adds conditions joined like the last row, and groups', async () => {
    const rows = [
      conditionRow(createCondition('text', 'contains', 'a')),
      conditionRow(createCondition('text', 'contains', 'b'), 'OR')
    ]
    const wrapper = mountBuilder(rows)

    await wrapper.get('.builder-actions button').trigger('click')
    expect(lastRows(wrapper).map(row => row.join)).toEqual(['AND', 'OR', 'OR'])

    await wrapper.findAll('.builder-actions button')[1].trigger('click')
    expect(lastRows(wrapper).slice(-1)[0]!.kind).toBe('group')
  })

  it('changes a join and removes a row', async () => {
    const rows = [
      conditionRow(createCondition('text', 'contains', 'a')),
      conditionRow(createCondition('text', 'contains', 'b'))
    ]
    const wrapper = mountBuilder(rows)

    await wrapper.get('[aria-label="Join with the row above"]').setValue('OR')
    expect(lastRows(wrapper)[1].join).toBe('OR')

    await wrapper.findAll('[aria-label="Remove condition"]')[0].trigger('click')
    expect(lastRows(wrapper)).toHaveLength(1)
  })

  it('drops a group whose last condition is removed', async () => {
    const wrapper = mountBuilder([
      conditionRow(createCondition('text', 'contains', 'a')),
      { kind: 'group', id: 'g', join: 'AND', rows: [conditionRow(createCondition('text', 'contains', 'b'))] }
    ])

    await wrapper.findAll('[aria-label="Remove condition"]')[1].trigger('click')
    expect(lastRows(wrapper)).toHaveLength(1)
  })
})
