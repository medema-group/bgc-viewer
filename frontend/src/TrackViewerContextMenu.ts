import * as d3 from 'd3';
import type { Selection } from 'd3-selection';

type Div = Selection<HTMLDivElement, unknown, any, any>;
type Span = Selection<HTMLSpanElement, unknown, any, any>;

export type MenuItem =
  | { type: 'separator' }
  | {
      type?: 'item';
      label: string;
      action?: () => void;
      // Shows a checkbox with this state; 'mixed' shows a partially checked box
      checked?: () => boolean | 'mixed';
      // Keep the menu open after the action, e.g. to toggle several checkboxes in a row
      keepOpen?: boolean;
      // Shows a submenu when hovering over the item
      children?: MenuItem[];
    };

export type ContextMenuCallbacks = {
  containerElement: HTMLElement;
  // Called each time the menu opens, so the items can reflect the current state
  getMenuItems: () => MenuItem[];
};

export type ContextMenuController = {
  destroy(): void;
  // Update the checkbox states of the open menu
  refresh(): void;
  toggle(): void;
};

const CHECK_COLOR = '#2196F3';
// Space kept between a menu and the edges of the browser window
const VIEWPORT_MARGIN = 8;
// Gap between the menu button and the menu
const BUTTON_GAP = 4;

export function initTrackViewerContextMenu(cb: ContextMenuCallbacks): ContextMenuController {
  const body = document.body || document.documentElement;

  // Track mouse position globally for menu hiding logic
  let lastMouseEvent: MouseEvent | null = null;
  const trackMouse = (e: MouseEvent) => {
    lastMouseEvent = e;
  };
  document.addEventListener('mousemove', trackMouse);

  // Ensure container has relative positioning for absolute child positioning
  const containerStyle = window.getComputedStyle(cb.containerElement);
  if (containerStyle.position === 'static') {
    d3.select(cb.containerElement).style('position', 'relative');
  }

  // Create menu button (hamburger/ellipsis icon)
  const button = d3.select(cb.containerElement)
    .append('div')
    .attr('class', 'track-viewer-menu-button')
    .attr('aria-label', 'Track viewer options menu')
    .attr('role', 'button')
    .attr('tabindex', '0')
    .style('position', 'absolute')
    .style('top', '8px')
    .style('right', '8px')
    .style('width', '32px')
    .style('height', '32px')
    .style('background', 'white')
    .style('border', '1px solid #ccc')
    .style('border-radius', '4px')
    .style('cursor', 'pointer')
    .style('display', 'flex')
    .style('align-items', 'center')
    .style('justify-content', 'center')
    .style('z-index', '100')
    .style('box-shadow', '0 2px 4px rgba(0,0,0,0.1)')
    .style('opacity', '0')
    .style('transition', 'opacity 0.2s')
    .style('pointer-events', 'none')
    .html('&#8942;')
    .style('font-size', '20px')
    .style('line-height', '1')
    .style('user-select', 'none');

  // Create context menu element attached to body (so it can overlap)
  const menu = d3.select(body)
    .append('div')
    .attr('class', 'track-viewer-context-menu')
    .style('display', 'none')
    .style('z-index', '1001');
  stylePanel(menu);

  // Checkboxes of the rendered menu, to update their state after an action
  let checkboxes: { element: Span; checked: () => boolean | 'mixed' }[] = [];

  function stylePanel(panel: Div) {
    panel
      .style('position', 'absolute')
      .style('background', 'white')
      .style('border', '1px solid #ccc')
      .style('border-radius', '4px')
      .style('box-shadow', '0 2px 8px rgba(0,0,0,0.15)')
      .style('padding', '4px 0')
      .style('min-width', '200px');
  }

  function renderCheckbox(element: Span, state: boolean | 'mixed') {
    if (state === true) element.html('&#10003;').style('background', CHECK_COLOR).style('color', 'white').style('border-color', CHECK_COLOR);
    else if (state === 'mixed') element.html('&#8722;').style('background', CHECK_COLOR).style('color', 'white').style('border-color', CHECK_COLOR);
    else element.html('').style('background', 'white').style('border-color', '#999');
  }

  function refresh() {
    checkboxes.forEach(({ element, checked }) => renderCheckbox(element, checked()));
  }

  function renderItems(panel: Div, items: MenuItem[]) {
    items.forEach(item => {
      if (item.type === 'separator') {
        panel.append('div')
          .style('height', '1px')
          .style('background', '#e0e0e0')
          .style('margin', '4px 0');
        return;
      }

      const menuItem = panel
        .append('div')
        .attr('class', 'track-viewer-menu-item')
        .style('position', 'relative')
        .style('padding', '8px 16px')
        .style('cursor', 'pointer')
        .style('user-select', 'none')
        .style('white-space', 'nowrap')
        .style('display', 'flex')
        .style('align-items', 'center')
        .style('gap', '8px');

      if (item.checked) {
        const checkbox = menuItem
          .append('span')
          .attr('class', 'menu-checkbox')
          .style('width', '16px')
          .style('height', '16px')
          .style('border', '1px solid #999')
          .style('border-radius', '3px')
          .style('display', 'inline-flex')
          .style('align-items', 'center')
          .style('justify-content', 'center')
          .style('flex-shrink', '0');
        checkboxes.push({ element: checkbox, checked: item.checked });
        renderCheckbox(checkbox, item.checked());
      }

      menuItem.append('span').style('flex', '1').text(item.label);

      let submenu: Div | null = null;
      if (item.children) {
        menuItem.append('span').attr('class', 'menu-submenu-arrow').style('color', '#666').html('&#9656;');
        submenu = menuItem
          .append('div')
          .attr('class', 'track-viewer-submenu')
          .style('display', 'none')
          .style('overflow-y', 'auto')
          .style('cursor', 'default');
        stylePanel(submenu);
        // Placed against the window, so a scrolling main menu doesn't clip it
        submenu.style('position', 'fixed');
        renderItems(submenu, item.children);
      }

      menuItem
        .on('mouseenter', function(this: HTMLElement) {
          d3.select(this).style('background', '#f5f5f5');
          if (submenu) showSubmenu(submenu);
        })
        .on('mouseleave', function(this: HTMLElement) {
          d3.select(this).style('background', 'transparent');
          submenu?.style('display', 'none');
        })
        .on('click', (event: MouseEvent) => {
          // Clicks in the submenu bubble up to here: its items handled them already,
          // and clicks elsewhere in it shouldn't close the menu
          if (submenu && (submenu.node() as HTMLElement).contains(event.target as Node)) {
            event.stopPropagation();
            return;
          }
          if (submenu) {
            // Toggle on click as well, for touch screens
            event.stopPropagation();
            if (submenu.style('display') === 'none') showSubmenu(submenu);
            else submenu.style('display', 'none');
            return;
          }
          if (typeof item.action === 'function') item.action();
          if (item.keepOpen) {
            event.stopPropagation();
            refresh();
          } else {
            hideMenu();
          }
        });
    });
  }

  // Open a submenu beside its item, on the side where it fits, and within the window: moved
  // up as far as needed, and scrolling when it is taller than the window
  function showSubmenu(submenu: Div) {
    const node = submenu.node() as HTMLElement;
    const item = node.parentElement!.getBoundingClientRect();
    submenu
      .style('display', 'block')
      .style('max-height', `${Math.max(0, window.innerHeight - 2 * VIEWPORT_MARGIN)}px`);
    const { width, height } = node.getBoundingClientRect();

    const fitsRight = item.right + width <= window.innerWidth - VIEWPORT_MARGIN;
    const fitsLeft = item.left - width >= VIEWPORT_MARGIN;
    const left = fitsRight || !fitsLeft ? item.right : item.left - width;
    // Its top lines up with the item's, as far as the window allows
    const top = item.top - 5;

    submenu
      .style('left', `${clamp(left, width, window.innerWidth)}px`)
      .style('top', `${clamp(top, height, window.innerHeight)}px`);
  }

  // A position along one axis that keeps a panel of the given size within the window,
  // preferring its start edge when the panel is too large to fit
  function clamp(position: number, size: number, windowSize: number): number {
    return Math.max(VIEWPORT_MARGIN, Math.min(position, windowSize - VIEWPORT_MARGIN - size));
  }

  // Show button on container hover
  d3.select(cb.containerElement)
    .on('mouseenter', () => {
      button.style('opacity', '1').style('pointer-events', 'all');
    })
    .on('mouseleave', () => {
      if (menu.style('display') === 'none') {
        button.style('opacity', '0').style('pointer-events', 'none');
      }
    });

  function showMenuBelowButton() {
    // Render the items afresh, as they may have changed since the menu was last open
    menu.selectAll('*').remove();
    checkboxes = [];
    renderItems(menu, cb.getMenuItems());

    const buttonRect = (button.node() as HTMLElement).getBoundingClientRect();
    // Add scroll offsets to get absolute position in document
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

    // A menu taller than the window scrolls
    menu
      .style('display', 'block')
      .style('max-height', `${Math.max(0, window.innerHeight - 2 * VIEWPORT_MARGIN)}px`)
      .style('overflow-y', 'auto');
    const { width, height } = (menu.node() as HTMLElement).getBoundingClientRect();

    // Right-aligned with the button, and below it; above it when it only fits there.
    // Otherwise it is moved up as far as needed to fit in the window.
    const below = buttonRect.bottom + BUTTON_GAP;
    const above = buttonRect.top - BUTTON_GAP - height;
    const top = below + height <= window.innerHeight - VIEWPORT_MARGIN || above < VIEWPORT_MARGIN ? below : above;
    const left = buttonRect.right - width;

    menu
      .style('top', `${clamp(top, height, window.innerHeight) + scrollTop}px`)
      .style('left', `${clamp(left, width, window.innerWidth) + scrollLeft}px`);
  }

  function hideMenu() {
    menu.style('display', 'none');

    // Only hide button if mouse is not currently over the container
    const containerRect = cb.containerElement.getBoundingClientRect();

    if (lastMouseEvent) {
      const mouseX = lastMouseEvent.clientX;
      const mouseY = lastMouseEvent.clientY;

      // Check if mouse is within container bounds
      const isMouseOverContainer =
        mouseX >= containerRect.left &&
        mouseX <= containerRect.right &&
        mouseY >= containerRect.top &&
        mouseY <= containerRect.bottom;

      if (!isMouseOverContainer) {
        button.style('opacity', '0').style('pointer-events', 'none');
      }
    } else {
      // If we don't have mouse position, keep button visible to be safe
      // It will hide on next mouseleave event anyway
    }
  }

  function toggle() {
    if (menu.style('display') === 'none') showMenuBelowButton();
    else hideMenu();
  }

  button.on('click', (event: MouseEvent) => {
    event.stopPropagation();
    toggle();
  });

  d3.select(body).on('click.trackviewer-context', () => {
    hideMenu();
  });

  return {
    destroy() {
      document.removeEventListener('mousemove', trackMouse);
      d3.select(cb.containerElement).on('mouseenter', null).on('mouseleave', null);
      d3.select(body).on('click.trackviewer-context', null);
      menu.remove();
      button.remove();
    },
    refresh,
    toggle
  };
}
