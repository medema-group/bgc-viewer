import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import { TrackViewer, MenuItem } from '../TrackViewer';

/**
 * Tests of the track viewer's options menu, with extra items supplied through the config
 */

describe('TrackViewer options menu', () => {
  let container: HTMLDivElement;
  let viewer: TrackViewer | null;

  const menu = () => document.querySelector('.track-viewer-context-menu') as HTMLElement;
  const openMenu = () => (document.querySelector('.track-viewer-menu-button') as HTMLElement).click();
  const findItem = (label: string) => Array.from(document.querySelectorAll<HTMLElement>('.track-viewer-menu-item'))
    .find(item => item.querySelector('span:not(.menu-checkbox):not(.menu-submenu-arrow)')?.textContent === label)!;
  const isChecked = (item: HTMLElement) => item.querySelector('.menu-checkbox')!.innerHTML;

  beforeEach(() => {
    global.ResizeObserver = vi.fn().mockImplementation(() => ({
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn(),
    }));
    container = document.createElement('div');
    document.body.appendChild(container);
    viewer = null;
  });

  afterEach(() => {
    viewer?.destroy();
    container.remove();
  });

  test('shows only the built-in items without extra items', () => {
    viewer = new TrackViewer({ container, width: 800 });
    openMenu();

    expect(menu().style.display).toBe('block');
    expect(findItem('Save as SVG')).toBeDefined();
    expect(findItem('Show track labels')).toBeDefined();
    expect(document.querySelector('.track-viewer-submenu')).toBeNull();
  });

  test('shows extra items in a submenu and runs their actions', () => {
    const zoom = vi.fn();
    viewer = new TrackViewer({
      container,
      width: 800,
      menuItems: () => [{ label: 'Zoom to', children: [{ label: 'Somewhere', action: zoom }] }]
    });
    openMenu();

    const parent = findItem('Zoom to');
    const submenu = parent.querySelector('.track-viewer-submenu') as HTMLElement;
    expect(submenu.style.display).toBe('none');
    parent.dispatchEvent(new MouseEvent('mouseenter'));
    expect(submenu.style.display).toBe('block');

    findItem('Somewhere').click();
    expect(zoom).toHaveBeenCalledOnce();
    expect(menu().style.display).toBe('none');
  });

  test('keeps the menu open and updates checkboxes for keepOpen items', () => {
    const selected = new Set(['a']);
    const toggle = (id: string) => selected.has(id) ? selected.delete(id) : selected.add(id);
    const items = (): MenuItem[] => [{
      label: 'Tracks',
      children: [
        { label: 'All', keepOpen: true, checked: () => selected.size === 2 || (selected.size > 0 && 'mixed'), action: () => {} },
        { label: 'A', keepOpen: true, checked: () => selected.has('a'), action: () => toggle('a') },
        { label: 'B', keepOpen: true, checked: () => selected.has('b'), action: () => toggle('b') }
      ]
    }];
    viewer = new TrackViewer({ container, width: 800, menuItems: items });
    openMenu();

    expect(isChecked(findItem('A'))).toBe('✓');
    expect(isChecked(findItem('B'))).toBe('');
    expect(isChecked(findItem('All'))).toBe('−');

    findItem('B').click();
    expect(menu().style.display).toBe('block');
    expect(isChecked(findItem('B'))).toBe('✓');
    expect(isChecked(findItem('All'))).toBe('✓');
  });

  test('reads the extra items each time the menu opens', () => {
    let label = 'First';
    viewer = new TrackViewer({ container, width: 800, menuItems: () => [{ label, action: () => {} }] });
    openMenu();
    expect(findItem('First')).toBeDefined();

    document.body.click();
    label = 'Second';
    openMenu();
    expect(findItem('First')).toBeUndefined();
    expect(findItem('Second')).toBeDefined();
  });
});
