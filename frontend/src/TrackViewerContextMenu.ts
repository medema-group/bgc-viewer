import * as d3 from 'd3';

export type ContextMenuCallbacks = {
  containerElement: HTMLElement;
  onSaveSVG: () => void;
  onSavePNG: () => void;
  getShowTrackLabels: () => boolean;
  getShowAllAnnotationLabels: () => boolean;
  onToggleTrackLabels: () => void;
  onToggleAllAnnotationLabels: () => void;
};

export type ContextMenuController = {
  destroy(): void;
  updateCheckbox(label: string, checked: boolean): void;
  toggle(): void;
};

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
    .style('position', 'absolute')
    .style('background', 'white')
    .style('border', '1px solid #ccc')
    .style('border-radius', '4px')
    .style('box-shadow', '0 2px 8px rgba(0,0,0,0.15)')
    .style('padding', '4px 0')
    .style('min-width', '200px')
    .style('display', 'none')
    .style('z-index', '1001');

  const menuItems: any[] = [
    { label: 'Save as SVG', action: cb.onSaveSVG },
    { label: 'Save as PNG', action: cb.onSavePNG },
    { type: 'separator' },
    { label: 'Show track labels', action: cb.onToggleTrackLabels, checkbox: true, checked: cb.getShowTrackLabels },
    { label: 'Show all annotation labels', action: cb.onToggleAllAnnotationLabels, checkbox: true, checked: cb.getShowAllAnnotationLabels }
  ];

  menuItems.forEach(item => {
    if (item.type === 'separator') {
      menu.append('div')
        .style('height', '1px')
        .style('background', '#e0e0e0')
        .style('margin', '4px 0');
    } else {
      const menuItem = menu
        .append('div')
        .attr('class', 'track-viewer-menu-item')
        .style('padding', '8px 16px')
        .style('cursor', 'pointer')
        .style('user-select', 'none')
        .style('display', 'flex')
        .style('align-items', 'center')
        .style('gap', '8px')
        .on('mouseenter', function(this: HTMLElement) {
            d3.select(this).style('background', '#f5f5f5');
          })
          .on('mouseleave', function(this: HTMLElement) {
            d3.select(this).style('background', 'transparent');
          })
        .on('click', () => {
          if (typeof item.action === 'function') item.action();
          hideMenu();
        });

      if (item.checkbox) {
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

        (item as any).checkboxElement = checkbox;
        if (item.checked && item.checked()) {
          checkbox.html('&#10003;').style('background', '#2196F3').style('color', 'white').style('border-color', '#2196F3');
        }
      }

      menuItem.append('span').text(item.label);
    }
  });

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

  function positionMenuBelowButton() {
    const buttonRect = (button.node() as HTMLElement).getBoundingClientRect();
    // Add scroll offsets to get absolute position in document
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
    
    menu.style('display', 'block')
      .style('top', `${buttonRect.bottom + scrollTop + 4}px`)
      .style('left', `${buttonRect.right + scrollLeft - 200}px`);
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

  button.on('click', (event: MouseEvent) => {
    event.stopPropagation();
    if (menu.style('display') === 'none') positionMenuBelowButton();
    else hideMenu();
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
    updateCheckbox(label: string, checked: boolean) {
      const item = menuItems.find(i => i.label === label);
      if (item && item.checkboxElement) {
        if (checked) item.checkboxElement.html('&#10003;').style('background', '#2196F3').style('color', 'white').style('border-color', '#2196F3');
        else item.checkboxElement.html('').style('background', 'white').style('border-color', '#999');
      }
    },
    toggle() {
      if (menu.style('display') === 'none') positionMenuBelowButton();
      else hideMenu();
    }
  };
}
