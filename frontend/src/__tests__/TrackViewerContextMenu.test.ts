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

  describe('placement within the window', () => {
    // jsdom has no layout: each element gets the box given here, by class
    let boxes: Record<string, { left: number; top: number; width: number; height: number }>;
    const rect = ({ left, top, width, height }: { left: number; top: number; width: number; height: number }) =>
      ({ left, top, width, height, right: left + width, bottom: top + height, x: left, y: top, toJSON: () => ({}) }) as DOMRect;

    beforeEach(() => {
      Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1000 });
      Object.defineProperty(window, 'innerHeight', { configurable: true, value: 600 });
      boxes = {};
      vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function(this: HTMLElement) {
        const name = Object.keys(boxes).find(className => this.classList.contains(className));
        return rect(name ? boxes[name] : { left: 0, top: 0, width: 0, height: 0 });
      });
    });

    afterEach(() => {
      vi.restoreAllMocks();
    });

    const twentyTracks = (): MenuItem[] => [{
      label: 'Tracks',
      children: Array.from({ length: 20 }, (_, i) => ({ label: `Track ${i}`, action: () => {} }))
    }];

    test('opens below the button, right-aligned with it', () => {
      boxes['track-viewer-menu-button'] = { left: 500, top: 100, width: 32, height: 32 };
      boxes['track-viewer-context-menu'] = { left: 0, top: 0, width: 200, height: 300 };
      viewer = new TrackViewer({ container, width: 800 });
      openMenu();

      expect(menu().style.top).toBe('136px');
      expect(menu().style.left).toBe('332px');
    });

    test('opens above the button when there is no room below it', () => {
      boxes['track-viewer-menu-button'] = { left: 500, top: 500, width: 32, height: 32 };
      boxes['track-viewer-context-menu'] = { left: 0, top: 0, width: 200, height: 300 };
      viewer = new TrackViewer({ container, width: 800 });
      openMenu();

      expect(menu().style.top).toBe('196px');
    });

    test('moves up as far as needed when it fits neither below nor above the button', () => {
      boxes['track-viewer-menu-button'] = { left: 100, top: 250, width: 32, height: 32 };
      boxes['track-viewer-context-menu'] = { left: 0, top: 0, width: 200, height: 400 };
      viewer = new TrackViewer({ container, width: 800 });
      openMenu();

      // Bottom at the window's height less the margin; left at the margin, not off the window
      expect(menu().style.top).toBe('192px');
      expect(menu().style.left).toBe('8px');
      expect(menu().style.maxHeight).toBe('584px');
    });

    test('keeps a long submenu within the window, scrolling it', () => {
      boxes['track-viewer-menu-button'] = { left: 900, top: 450, width: 32, height: 32 };
      boxes['track-viewer-context-menu'] = { left: 0, top: 0, width: 200, height: 50 };
      boxes['track-viewer-menu-item'] = { left: 732, top: 490, width: 200, height: 36 };
      boxes['track-viewer-submenu'] = { left: 0, top: 0, width: 220, height: 584 };
      viewer = new TrackViewer({ container, width: 800, menuItems: twentyTracks });
      openMenu();

      const parent = findItem('Tracks');
      const submenu = parent.querySelector('.track-viewer-submenu') as HTMLElement;
      parent.dispatchEvent(new MouseEvent('mouseenter'));

      // No room to the right of the item, so it opens to its left; moved up to fit the window
      expect(submenu.style.position).toBe('fixed');
      expect(submenu.style.left).toBe('512px');
      expect(submenu.style.top).toBe('8px');
      expect(submenu.style.maxHeight).toBe('584px');
    });
  });
});
