import * as d3 from 'd3';
import type { Selection, EnterElement } from 'd3-selection';
import type { ScaleLinear } from 'd3-scale';
import type { ZoomBehavior, ZoomTransform, D3ZoomEvent } from 'd3-zoom';
import { initTrackViewerContextMenu } from './TrackViewerContextMenu';
import type { MenuItem, ContextMenuController } from './TrackViewerContextMenu';

export type { MenuItem };

export type TrackData = {
  id: string;
  label: string;
  height?: number; // Optional per-track height, falls back to config.trackHeight
}

export type AnnotationType = 'arrow' | 'box' | 'circle' | 'triangle' | 'pin';

export type AnnotationData = {
  id: string;
  trackId: string;
  type: AnnotationType;
  classes: string[];
  label: string;
  labelPosition?: 'above' | 'center';
  showLabel?: 'hover' | 'always' | 'never' | 'auto'; // 'auto': always if it doesn't overlap other labels, else hover
  start: number;
  end: number;
  fy?: number; // Fractional y position of the annotation, default is 0.5
               // (anchor is center for boxes/arrows or focal position for markers)
  heightFraction?: number; // Fraction of track height
  direction?: 'left' | 'right';
  fill?: string;
  stroke?: string;
  opacity?: number;
  corner_radius?: number;
  tooltip?: string; // Optional custom tooltip content
  zoomOnDoubleClick?: boolean; // Zoom to the annotation when double clicked, default true for boxes and arrows
  data?: any; // Optional reference to original data object
}

export type DrawingPrimitiveType = 'horizontal-line' | 'background';

export type DrawingPrimitive = {
  id: string;
  trackId: string;
  type: DrawingPrimitiveType;
  class: string;
  start?: number;
  end?: number;
  fy?: number; // Fractional vertical position (0 to 1)
  stroke?: string;
  fill?: string;
  opacity?: number;
}

export type TrackViewerData = {
  tracks: TrackData[];
  annotations: AnnotationData[];
  primitives?: DrawingPrimitive[];
}

export interface TrackViewerConfig {
  container: string | HTMLElement;
  width?: number;
  height?: number;
  margin?: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
  trackHeight?: number;
  domain?: [number, number];
  zoomExtent?: [number, number];
  showTrackLabels?: boolean;
  onAnnotationClick?: (annotation: AnnotationData, track: TrackData) => void;
  onAnnotationHover?: (annotation: AnnotationData, track: TrackData, event: MouseEvent) => void;
  onBackgroundClick?: () => void;
  onDomainChange?: (domain: [number, number]) => void;
  // Extra items shown at the top of the options menu, read each time the menu opens
  menuItems?: () => MenuItem[];
}


export class TrackViewer {
  private config: Required<TrackViewerConfig>;
  private svg!: Selection<SVGSVGElement, unknown, null, undefined>;
  private chart!: Selection<SVGGElement, unknown, null, undefined>;
  private clippedChart!: Selection<SVGGElement, unknown, null, undefined>;
  private xAxisGroup!: Selection<SVGGElement, unknown, null, undefined>;
  private tooltip!: Selection<HTMLDivElement, unknown, null, undefined>;
  private x!: ScaleLinear<number, number>;
  private currentTransform: ZoomTransform;
  private zoom!: ZoomBehavior<SVGSVGElement, unknown>;
  private data: TrackViewerData = { tracks: [], annotations: [], primitives: [] };
  private trackGroups!: Selection<SVGGElement, TrackData, SVGGElement, unknown>;
  private clipId!: string;
  private originalLeftMargin: number; // Store original left margin
  private isResponsiveWidth: boolean; // Track if width should be responsive
  private containerElement!: HTMLElement; // Store reference to container
  private resizeHandler?: () => void; // Store resize handler for cleanup
  private resizeObserver?: ResizeObserver; // Store ResizeObserver for cleanup
  private static readonly LABEL_PADDING = 24; // Padding for labels that extend above tracks
  private static readonly ZOOM_TO_ANNOTATION_FILL = 0.75; // Fraction of the view an annotation zoomed to takes up, the rest is split as margin on both sides
  private contextMenuController?: ContextMenuController;
  private showTrackLabels: boolean;
  private showAllAnnotationLabels: boolean = false;
  private labelGroups!: Selection<SVGGElement, TrackData, SVGGElement, unknown>;
  private isDragging: boolean = false;
  private lastAnnotationClick: { id: string; time: number } | null = null;
  private lastAnnotationDoubleClickTime: number = -Infinity;
  private static readonly DOUBLE_CLICK_INTERVAL = 500; // Max ms between the clicks of a double click

  constructor(config: TrackViewerConfig) {
    // Check if width was explicitly provided
    this.isResponsiveWidth = config.width === undefined;
    
    // Get container element early to calculate responsive width
    const containerElement = typeof config.container === 'string' 
      ? document.querySelector(config.container)
      : config.container;

    if (!containerElement) {
      throw new Error('Container element not found');
    }
    this.containerElement = containerElement as HTMLElement;

    // Calculate responsive width if not explicitly set
    const calculatedWidth = this.isResponsiveWidth 
      ? this.calculateResponsiveWidth()
      : (config.width || 800);

    // Determine default left margin based on showTrackLabels setting
    const defaultLeftMargin = (config.showTrackLabels !== false) ? 60 : 10;
    const margin = config.margin || { top: 20, right: 10, bottom: 20, left: defaultLeftMargin };

    // Set default configuration
    this.config = {
      container: config.container,
      width: calculatedWidth,
      height: config.height || 300,
      margin: margin,
      trackHeight: config.trackHeight || 30,
      domain: config.domain || [0, 100],
      zoomExtent: config.zoomExtent || [0.5, 20],
      showTrackLabels: config.showTrackLabels !== undefined ? config.showTrackLabels : true,
      onAnnotationClick: config.onAnnotationClick || (() => {}),
      onAnnotationHover: config.onAnnotationHover || (() => {}),
      onBackgroundClick: config.onBackgroundClick || (() => {}),
      onDomainChange: config.onDomainChange || (() => {}),
      menuItems: config.menuItems || (() => [])
    };

    // Store the original left margin as minimum
    this.originalLeftMargin = this.config.margin.left;

    // Initialize showTrackLabels from config
    this.showTrackLabels = this.config.showTrackLabels;

    // If track labels are hidden from the start, use minimal margin
    if (!this.showTrackLabels) {
      this.config.margin.left = this.originalLeftMargin;
    }

    this.currentTransform = d3.zoomIdentity;
    this.initialize();
    
    // Set up automatic resize handling for responsive width
    if (this.isResponsiveWidth) {
      this.setupAutoResize();
    }
  }

  private calculateResponsiveWidth(): number {
    // Calculate width based on container, leaving some margin
    const containerWidth = this.containerElement.clientWidth || 800;
    return Math.max(600, containerWidth - 40); // 20px margin on each side, minimum 600px
  }

  private setupAutoResize(): void {
    let resizeTimeout: NodeJS.Timeout;
    
    // Use ResizeObserver to watch for container size changes
    // This handles both window resizes AND container resizes (e.g., from draggable dividers)
    this.resizeObserver = new ResizeObserver((entries) => {
      // Throttle resize events to avoid excessive recalculation
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        this.resize();
      }, 100);
    });
    
    // Observe the container element
    this.resizeObserver.observe(this.containerElement);
  }

  private initialize(): void {
    // Get container element
    const containerElement = typeof this.config.container === 'string' 
      ? document.querySelector(this.config.container)
      : this.config.container;

    if (!containerElement) {
      throw new Error('Container element not found');
    }

    // Create tooltip
    const body = document.body || document.documentElement;
    this.tooltip = d3.select(body)
      .append('div')
      .attr('class', 'track-viewer-tooltip')
      .style('position', 'absolute')
      .style('background', 'white')
      .style('border', '1px solid #ccc')
      .style('padding', '4px 8px')
      .style('pointer-events', 'none')
      .style('display', 'none')
      .style('z-index', '1000');

    // Create SVG
    this.svg = d3.select(containerElement)
      .append('svg')
      .attr('width', this.config.width)
      .attr('height', this.config.height);

    // Create chart group
    this.chart = this.svg
      .append('g')
      .attr('transform', `translate(${this.config.margin.left},${this.config.margin.top})`);

    // Create clipping path to prevent annotations from overlapping labels
    const chartWidth = this.config.width - this.config.margin.left - this.config.margin.right;
    this.clipId = `clip-${Math.random().toString(36).substring(2, 11)}`;
    
    this.svg
      .append('defs')
      .append('clipPath')
      .attr('id', this.clipId)
      .append('rect')
      .attr('x', 0)
      .attr('y', -TrackViewer.LABEL_PADDING) // Add padding above for labels
      .attr('width', chartWidth)
      .attr('height', '100%'); // Will be updated when height changes

    // Create x-axis group (unclipped, so axis labels can extend)
    this.xAxisGroup = this.chart
      .append('g')
      .attr('class', 'x-axis');

    // Create clipped container for track content
    this.clippedChart = this.chart
      .append('g')
      .attr('clip-path', `url(#${this.clipId})`);

    // Initialize x scale
    this.x = d3.scaleLinear()
      .domain(this.config.domain)
      .range([0, this.config.width - this.config.margin.left - this.config.margin.right]);

    // Initialize zoom behavior
    this.initializeZoom();

    // Create context menu UI (delegated to separate module)
    this.createContextMenu();
  }
  private initializeZoom(): void {
    const chartWidth = this.config.width - this.config.margin.left - this.config.margin.right;
    const chartHeight = this.config.height - this.config.margin.top - this.config.margin.bottom;

    this.zoom = (d3.zoom() as ZoomBehavior<SVGSVGElement, unknown>)
      .scaleExtent(this.config.zoomExtent)
      .translateExtent([[0, 0], [chartWidth, chartHeight]])
      .extent([[0, 0], [chartWidth, chartHeight]])
      // Without some tolerance, the slightest mouse movement turns a click into a pan,
      // and d3 then suppresses the click event
      .clickDistance(4)
      .filter((event: any) => {
        // Track when dragging starts (mousedown without wheel)
        if (event.type === 'mousedown' && event.button === 0) {
          this.isDragging = true;
        }
        // Reset dragging flag on mouseup
        if (event.type === 'mouseup') {
          this.isDragging = false;
        }
        // Skip d3's double-click zoom when an annotation was just double clicked
        if (event.type === 'dblclick' && Date.now() - this.lastAnnotationDoubleClickTime < TrackViewer.DOUBLE_CLICK_INTERVAL) {
          return false;
        }
        // Allow default zoom behavior
        return !event.ctrlKey && !event.button;
      })
      .on('zoom', (event: D3ZoomEvent<SVGSVGElement, unknown>) => {
        this.currentTransform = event.transform;
        this.drawTracks();
        
        // Notify about domain change
        const domain = this.getCurrentDomain();
        this.config.onDomainChange(domain);
      })
      .on('start', (event: any) => {
        // Only change cursor to grabbing if it's a drag (not a wheel zoom)
        if (event.sourceEvent && event.sourceEvent.type === 'mousedown') {
          this.clippedChart.select('.chart-background').style('cursor', 'grabbing');
          this.svg.style('cursor', 'grabbing');
        }
      })
      .on('end', () => {
        this.isDragging = false;
        this.clippedChart.select('.chart-background').style('cursor', 'grab');
        this.svg.style('cursor', '');
      });

    // Apply zoom behavior to the main SVG instead of an overlay
    // This allows individual elements to handle their own mouse events
    this.svg.call(this.zoom);

    // Create a background rect for empty areas to still capture zoom events
    this.clippedChart
      .insert('rect', ':first-child')
      .attr('class', 'chart-background')
      .attr('width', chartWidth)
      .attr('height', chartHeight)
      .attr('y', -TrackViewer.LABEL_PADDING) // Start above to match clipPath
      .style('fill', 'transparent')
      .style('pointer-events', 'all')
      .style('cursor', 'grab')
      .on('click', () => {
        this.config.onBackgroundClick();
      });
  }
  
  private createContextMenu(): void {
    this.contextMenuController = initTrackViewerContextMenu({
      containerElement: this.containerElement,
      getMenuItems: () => {
        const extraItems = this.config.menuItems();
        return [
          ...extraItems,
          ...(extraItems.length > 0 ? [{ type: 'separator' as const }] : []),
          { label: 'Save as SVG', action: () => this.saveAsSVG() },
          { label: 'Save as PNG', action: () => this.saveAsPNG() },
          { type: 'separator' },
          { label: 'Show track labels', action: () => this.toggleTrackLabels(), checked: () => this.showTrackLabels },
          { label: 'Show all annotation labels', action: () => this.toggleAllAnnotationLabels(), checked: () => this.showAllAnnotationLabels }
        ];
      }
    });
  }

  private saveAsSVG(): void {
    // Clone the SVG node
    const svgNode = this.svg.node();
    if (!svgNode) return;

    const svgClone = svgNode.cloneNode(true) as SVGSVGElement;
    
    // Apply inline styles from CSS to the clone
    const styleText = this.getInlineStyles(svgClone);
    
    // Add styles inline for standalone SVG
    const styleElement = document.createElementNS('http://www.w3.org/2000/svg', 'style');
    styleElement.textContent = styleText;
    svgClone.insertBefore(styleElement, svgClone.firstChild);

    // Clean up data-styled attributes from clone
    d3.select(svgClone).selectAll('[data-styled]').attr('data-styled', null);

    // Serialize to string
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svgClone);
    
    // Create blob and download
    const blob = new Blob([svgString], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'track-viewer.svg';
    link.click();
    URL.revokeObjectURL(url);
  }

  private saveAsPNG(): void {
    const svgNode = this.svg.node();
    if (!svgNode) return;

    const svgClone = svgNode.cloneNode(true) as SVGSVGElement;
    
    // Apply inline styles from CSS to the clone
    const styleText = this.getInlineStyles(svgClone);
    
    // Add styles inline
    const styleElement = document.createElementNS('http://www.w3.org/2000/svg', 'style');
    styleElement.textContent = styleText;
    svgClone.insertBefore(styleElement, svgClone.firstChild);

    // Clean up data-styled attributes from clone
    d3.select(svgClone).selectAll('[data-styled]').attr('data-styled', null);

    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svgClone);
    
    // Create canvas with margin
    const margin = 20; // 20px margin on all sides
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size with higher resolution for better quality + margin
    const scale = 2;
    canvas.width = (this.config.width + margin * 2) * scale;
    canvas.height = (this.config.height + margin * 2) * scale;
    ctx.scale(scale, scale);

    // Create image from SVG
    const img = new Image();
    const blob = new Blob([svgString], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    
    img.onload = () => {
      // Fill white background
      ctx.fillStyle = 'white';
      ctx.fillRect(0, 0, this.config.width + margin * 2, this.config.height + margin * 2);
      
      // Draw image with margin offset
      ctx.drawImage(img, margin, margin);
      URL.revokeObjectURL(url);
      
      // Convert to PNG and download
      canvas.toBlob((pngBlob) => {
        if (pngBlob) {
          const pngUrl = URL.createObjectURL(pngBlob);
          const link = document.createElement('a');
          link.href = pngUrl;
          link.download = 'track-viewer.png';
          link.click();
          URL.revokeObjectURL(pngUrl);
        }
      });
    };
    
    img.src = url;
  }

  private getInlineStyles(svgElement: SVGSVGElement = this.svg.node()!): string {
    // Get all stylesheets
    const sheets = Array.from(document.styleSheets);
    const cssRules: string[] = [];

    // Extract CSS rules that might apply to SVG content
    sheets.forEach(sheet => {
      try {
        // Check if we can access the stylesheet (same-origin policy)
        const rules = sheet.cssRules || sheet.rules;
        if (rules) {
          Array.from(rules).forEach((rule: any) => {
            if (rule.selectorText) {
              // Include rules that target SVG-related classes or elements
              const selector = rule.selectorText;
              if (
                selector.includes('.track') ||
                selector.includes('.annotation') ||
                selector.includes('.axis') ||
                selector.includes('.primitive') ||
                selector.includes('svg') ||
                selector.includes('text') ||
                selector.includes('rect') ||
                selector.includes('path') ||
                selector.includes('circle') ||
                selector.includes('line') ||
                selector.includes('polygon')
              ) {
                cssRules.push(rule.cssText);
              }
            }
          });
        }
      } catch (e) {
        // Skip stylesheets we can't access (e.g., cross-origin)
      }
    });

    // Work with the provided SVG element (could be clone or original)
    const svg = d3.select(svgElement);

    // Get styles from track labels
    svg.selectAll<SVGTextElement, unknown>('.track-label').each(function() {
      const element = this as SVGTextElement;
      const computed = window.getComputedStyle(element);
      if (!element.hasAttribute('data-styled')) {
        element.setAttribute('data-styled', 'true');
        element.setAttribute('style', 
          `font-family: ${computed.fontFamily}; ` +
          `font-size: ${computed.fontSize}; ` +
          `fill: ${computed.fill || 'currentColor'};`
        );
      }
    });

    // Get styles from annotations and primitives - apply to actual shape elements, not container groups
    svg.selectAll<SVGElement, unknown>('.annotation, .primitive').each(function() {
      const container = this as SVGElement;
      const containerComputed = window.getComputedStyle(container);
      
      // Convert data-label to title element for exported SVG tooltips
      const containerLabel = container.getAttribute('data-label');
      if (containerLabel && !container.querySelector('title')) {
        const titleElement = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        titleElement.textContent = containerLabel;
        container.insertBefore(titleElement, container.firstChild);
        container.removeAttribute('data-label');
      }
      
      // Find the actual shape element(s) inside the container (path, rect, circle, line, polygon, etc.)
      const shapeElements = container.querySelectorAll('path, rect, circle, line, polygon, ellipse');
      
      shapeElements.forEach((shapeElement: Element) => {
        const shape = shapeElement as SVGElement;
        const computed = window.getComputedStyle(shape);
        
        if (!shape.hasAttribute('data-styled')) {
          shape.setAttribute('data-styled', 'true');
          const styleProps: string[] = [];
          
          // For fill: use the shape's computed fill, or fall back to container's fill if shape has none/default
          const shapeFill = computed.fill;
          const containerFill = containerComputed.fill;
          if (shapeFill && shapeFill !== 'none' && shapeFill !== 'rgb(0, 0, 0)') {
            // Shape has explicit fill
            styleProps.push(`fill: ${shapeFill}`);
          } else if (containerFill && containerFill !== 'none' && containerFill !== 'rgb(0, 0, 0)') {
            // Use container's fill (inherited)
            styleProps.push(`fill: ${containerFill}`);
          }
          
          if (computed.stroke && computed.stroke !== 'none') styleProps.push(`stroke: ${computed.stroke}`);
          if (computed.strokeWidth) styleProps.push(`stroke-width: ${computed.strokeWidth}`);
          if (computed.opacity && computed.opacity !== '1') styleProps.push(`opacity: ${computed.opacity}`);
          
          if (styleProps.length > 0) {
            const existingStyle = shape.getAttribute('style') || '';
            shape.setAttribute('style', existingStyle + ' ' + styleProps.join('; ') + ';');
          }
        }
      });
    });

    // Return combined CSS
    return cssRules.join('\n');
  }

  private toggleTrackLabels(): void {
    this.showTrackLabels = !this.showTrackLabels;
    
    // Toggle visibility of the entire labels container
    const labelsContainer = this.chart.select('.track-labels-container');
    labelsContainer.style('display', this.showTrackLabels ? '' : 'none');
    
    // Adjust left margin based on label visibility
    if (this.showTrackLabels) {
      // Restore the calculated margin for labels
      this.updateMarginAndLayout();
    } else {
      // Use minimal margin when labels are hidden
      this.config.margin.left = this.originalLeftMargin;
      this.updateChartWidth();
    }
  }

  // Apply a changed width or left margin to the chart area, while keeping the visible domain
  private updateChartWidth(): void {
    const domain = this.getCurrentDomain();
    const chartWidth = this.config.width - this.config.margin.left - this.config.margin.right;
    const chartHeight = this.config.height - this.config.margin.top - this.config.margin.bottom;

    this.chart.attr('transform', `translate(${this.config.margin.left},${this.config.margin.top})`);
    this.x.range([0, chartWidth]);
    this.svg.select('clipPath rect').attr('width', chartWidth);
    this.clippedChart.select('.chart-background').attr('width', chartWidth);
    this.zoom
      .translateExtent([[0, 0], [chartWidth, chartHeight]])
      .extent([[0, 0], [chartWidth, chartHeight]]);

    // The zoom transform is in pixels, so it has to be adjusted to the new range to keep
    // showing the same domain. This triggers a zoom event, which redraws the tracks.
    const k = this.currentTransform.k;
    const transform = d3.zoomIdentity
      .translate(-this.x(domain[0]) * k, this.currentTransform.y)
      .scale(k);
    this.svg.call(this.zoom.transform, transform);
  }

  private toggleAllAnnotationLabels(): void {
    this.showAllAnnotationLabels = !this.showAllAnnotationLabels;
    
    // Update all annotation labels in the labels layer
    this.clippedChart.selectAll<SVGGElement, unknown>('.annotation-labels-layer .annotation-label-group')
      .each((_, i, nodes) => this.applyLabelVisibility(d3.select(nodes[i])));
  }

  // Show or hide a label group according to its showLabel mode and the
  // showAllAnnotationLabels toggle (hover is handled by the annotation's event handlers)
  private applyLabelVisibility(labelGroup: Selection<SVGGElement, unknown, null, undefined>): void {
    const label = labelGroup.select('.annotation-label');
    const showLabel = label.attr('data-show-label');

    let visible: boolean;
    if (showLabel === 'always') {
      visible = true;
    } else if (showLabel === 'never') {
      visible = false;
    } else if (this.showAllAnnotationLabels) {
      visible = true;
    } else if (showLabel === 'auto') {
      // Set by updateAutoLabelFits()
      visible = label.attr('data-fits') === 'true';
    } else {
      // 'hover'
      visible = false;
    }
    labelGroup.style('display', visible ? '' : 'none');
  }
 

  // Helper methods for track heights
  private getTrackHeight(track: TrackData): number {
    return track.height || this.config.trackHeight;
  }

  private getTotalTracksHeight(): number {
    return this.data.tracks.reduce((total, track) => total + this.getTrackHeight(track), 0);
  }

  private getTrackYPosition(trackIndex: number): number {
    let y = 0;
    for (let i = 0; i < trackIndex; i++) {
      y += this.getTrackHeight(this.data.tracks[i]);
    }
    return y;
  }

  private updateHeight(): void {
    const newHeight = this.getTotalTracksHeight() + this.config.margin.top + this.config.margin.bottom;
    this.config.height = newHeight;
    this.svg.attr('height', newHeight);

    // Update x-axis position
    const chartHeight = this.getTotalTracksHeight();
    this.xAxisGroup.attr('transform', `translate(0, ${chartHeight})`);

    // Update clipping path height
    this.svg.select('clipPath rect')
      .attr('height', chartHeight + TrackViewer.LABEL_PADDING); // Add padding for labels

    // Update chart background height
    this.clippedChart.select('.chart-background')
      .attr('height', chartHeight + TrackViewer.LABEL_PADDING); // Add padding for labels
  }

  private createTrackGroups(): void {
    this.trackGroups = this.clippedChart
      .selectAll<SVGGElement, TrackData>('.track')
      .data(this.data.tracks, (d: TrackData) => d.id)
      .join('g')
      .attr('id', (d: TrackData) => d.id)
      .attr('class', 'track')
      .attr('transform', (_: TrackData, i: number) => `translate(0, ${this.getTrackYPosition(i)})`);

    // Create or select a single container group for all track labels
    let labelsContainer = this.chart.select<SVGGElement>('.track-labels-container');
    if (labelsContainer.empty()) {
      labelsContainer = this.chart
        .append('g')
        .attr('class', 'track-labels-container');
    }
    labelsContainer.style('display', this.showTrackLabels ? '' : 'none');

    // Add track labels (these should be outside the clipped area)
    this.labelGroups = labelsContainer
      .selectAll<SVGGElement, TrackData>('.track-label-group')
      .data(this.data.tracks, (d: TrackData) => d.id)
      .join('g')
      .attr('id', (d: TrackData) => `${d.id}-label`)
      .attr('class', 'track-label-group')
      .attr('transform', (_: TrackData, i: number) => `translate(0, ${this.getTrackYPosition(i)})`);

    this.labelGroups
      .selectAll('.track-label')
      .data((d: TrackData) => [d])
      .join('text')
      .attr('class', 'track-label')
      .attr('x', -10)
      .attr('y', (d: TrackData) => this.getTrackHeight(d) / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .text((d: TrackData) => d.label);
  }

  private drawTracks(): void {
    const xz = this.currentTransform.rescaleX(this.x);

    // Update axis
    this.xAxisGroup.call(d3.axisBottom(xz));
    
    // Add CSS class to axis text for styling
    this.xAxisGroup.selectAll('text')
      .attr('class', 'axis-label');

    // Early return if no tracks have been created yet
    if (!this.trackGroups) {
      return;
    }

    // Collect all labels data to render them in a separate layer on top
    const allLabelsData: Array<{ annotation: AnnotationData; trackData: TrackData; x: number; y: number; width: number; height: number; trackY: number }> = [];

    // Update annotations and primitives for each track
    this.trackGroups.each((trackData: TrackData, trackIndex: number, trackNodes: SVGGElement[] | ArrayLike<SVGGElement>) => {
      const trackGroup = d3.select(trackNodes[trackIndex]);
      const trackY = this.getTrackYPosition(trackIndex);

      // Get annotations and primitives for this track
      const trackAnnotations = this.data.annotations.filter(ann => ann.trackId === trackData.id);
      const trackPrimitives = (this.data.primitives || []).filter(prim => prim.trackId === trackData.id);

      // Combine primitives and annotations into a single array for rendering
      // Primitives go first so they render behind annotations
      const allElements: Array<{ type: 'primitive'; data: DrawingPrimitive } | { type: 'annotation'; data: AnnotationData }> = [
        ...trackPrimitives.map(p => ({ type: 'primitive' as const, data: p })),
        ...trackAnnotations.map(a => ({ type: 'annotation' as const, data: a }))
      ];

      // Use proper D3 data binding to manage element lifecycle
      type ElementType = { type: 'primitive'; data: DrawingPrimitive } | { type: 'annotation'; data: AnnotationData };
      const elementGroups = (trackGroup
        .selectAll('g.element') as Selection<SVGGElement, ElementType, SVGGElement, unknown>)
        .data(allElements, (d: ElementType) => d.data.id)
        .join(
          // Enter: create new groups
          (enter: Selection<EnterElement, ElementType, SVGGElement, unknown>) => enter.append('g'),
          // Update: existing groups (no action needed)
          (update: Selection<SVGGElement, ElementType, SVGGElement, unknown>) => update,
          // Exit: remove groups that are no longer in data
          (exit: Selection<SVGGElement, ElementType, SVGGElement, unknown>) => exit.remove()
        )
        .attr('id', (d: ElementType) => d.data.id)
        .attr('class', (d: ElementType) => {
          if (d.type === 'primitive') {
            return `element ${d.type} ${d.data.type} ${d.data.class}`;
          } else {
            return `element ${d.type} ${d.data.type} ${d.data.classes.join(' ')}`;
          }
        });

      // Clear existing content in each group and render
      const self = this;
      elementGroups.each(function(this: SVGGElement, d: ElementType) {
        const group = d3.select(this) as Selection<SVGGElement, unknown, null, undefined>;
        
        // Clear the group content
        group.selectAll('*').remove();
        
        // Render the element
        if (d.type === 'primitive') {
          self.renderPrimitive(group, d.data, xz, trackData);
        } else {
          self.renderAnnotation(group, d.data, xz, trackData, allLabelsData, trackY);
        }
      });
    });

    // Render all labels in a separate layer on top
    this.renderAllLabels(allLabelsData, xz);
  }

  private renderAnnotation(
    container: Selection<SVGGElement, unknown, null, undefined>,
    annotation: AnnotationData,
    xScale: ScaleLinear<number, number>,
    trackData: TrackData,
    labelsData?: Array<{ annotation: AnnotationData; trackData: TrackData; x: number; y: number; width: number; height: number; trackY: number }>,
    trackY: number = 0
  ): void {
    const x = xScale(annotation.start);
    const width = Math.max(1, xScale(annotation.end) - xScale(annotation.start));
    
    const trackHeight = this.getTrackHeight(trackData);
    
    // Calculate height based on heightFraction if provided, otherwise use default
    const height = annotation.heightFraction !== undefined 
      ? trackHeight * annotation.heightFraction
      : trackHeight / 2;
    
    // Center the annotation vertically in the track
    //const cy = (trackHeight - height) / 2;
    const y = trackHeight - (annotation.fy !== undefined ? annotation.fy * trackHeight : trackHeight / 2); // Use custom fy or center of track


    let element: Selection<any, unknown, null, undefined>;

    switch (annotation.type) {
      case 'arrow':
        element = this.renderArrow(container, x, y, width, height, annotation.direction);
        break;
      case 'circle':
        element = this.renderCircle(container, x, y, height);
        break;
      case 'triangle':
        element = this.renderTriangle(container, x, y, height);
        break;
      case 'pin':
        element = this.renderPin(container, x, y, height);
        break;
      case 'box':
      default:
        element = this.renderBox(container, x, y, width, height, annotation.corner_radius || 0);
        break;
    }

    // Put an opaque copy of the shape underneath, so that primitives (e.g. a horizontal line)
    // don't show through when the annotation is semi-transparent
    if (annotation.type !== 'pin') {
      element.clone(false)
        .attr('class', 'annotation-backdrop')
        .style('fill', 'white')
        .style('stroke', 'white')
        .style('pointer-events', 'none')
        .lower();
    }

    // Apply common styling and event handlers
    // Set data-label on the container (the group with .annotation class) for export
    container.attr('data-label', annotation.label);
    
    element
      .attr('data-annotation-id', annotation.id) // Add data attribute for label handling
      .style('cursor', 'pointer')
      .style('pointer-events', 'all'); // Ensure annotations can receive mouse events

    // Apply custom fill and stroke if specified
    if (annotation.fill) {
      element.style('fill', annotation.fill);
    }
    if (annotation.stroke) {
      element.style('stroke', annotation.stroke);
    }
    if (annotation.opacity !== undefined) {
      element.style('opacity', annotation.opacity);
    }

    element
      .on('mouseover', (event: any) => {
        // Don't change appearance if we're currently dragging
        if (this.isDragging) return;
        
        element.classed('hovered', true);
        // Show hidden labels (with a background) on hover - find label in the labels layer
        this.clippedChart.selectAll<SVGGElement, unknown>(`.annotation-label-group[data-annotation-id="${annotation.id}"]`)
          .filter(function() { return this.style.display === 'none'; })
          .style('display', 'block')
          .select('.annotation-label-background')
          .style('display', '');
        // Only show tooltip if tooltip content is provided
        if (annotation.tooltip !== undefined) {
          this.showTooltip(event, annotation, trackData);
        }
        this.config.onAnnotationHover(annotation, trackData, event);
      })
      .on('mouseout', () => {
        element.classed('hovered', false);
        // Hide hover labels if needed, but respect the showAllAnnotationLabels toggle
        this.clippedChart.selectAll<SVGGElement, unknown>(`.annotation-label-group[data-annotation-id="${annotation.id}"]`)
          .each((_, i, nodes) => {
            const labelGroup = d3.select(nodes[i]);
            this.applyLabelVisibility(labelGroup);
            // Always hide background on mouseout
            labelGroup.select('.annotation-label-background').style('display', 'none');
          });
        // Always try to hide tooltip on mouseout
        this.hideTooltip();
      });

    // Handle clicks on the container rather than on the shape: the shape is recreated on every
    // redraw, so if a (small) pan happens between mousedown and mouseup, the click is
    // dispatched to the container instead
    container.on('click', () => {
      this.config.onAnnotationClick(annotation, trackData);
      this.handlePossibleDoubleClick(annotation);
    });

    // Collect label data for rendering in a separate layer
    if (labelsData && annotation.label && annotation.showLabel !== 'never') {
      labelsData.push({ annotation, trackData, x, y, width, height, trackY });
    }
  }

  // Double clicking a box or arrow zooms to it (its clicks have selected it already). Double
  // clicks are detected from the clicks rather than with dblclick events: a click usually leads
  // to a redraw, which replaces the clicked shape, and then browsers don't see the next click
  // on the new shape as part of a double click.
  private handlePossibleDoubleClick(annotation: AnnotationData): void {
    const now = Date.now();
    const isDoubleClick = this.lastAnnotationClick?.id === annotation.id
      && now - this.lastAnnotationClick.time < TrackViewer.DOUBLE_CLICK_INTERVAL;
    // A third click starts a new double click, rather than completing another one
    this.lastAnnotationClick = isDoubleClick ? null : { id: annotation.id, time: now };
    if (!isDoubleClick) return;

    // Other annotations are points, so they keep d3's default double-click zoom
    const zoomOnDoubleClick = annotation.zoomOnDoubleClick ?? (annotation.type === 'box' || annotation.type === 'arrow');
    if (!zoomOnDoubleClick) return;

    this.lastAnnotationDoubleClickTime = now;
    const length = annotation.end - annotation.start;
    const margin = length * (1 - TrackViewer.ZOOM_TO_ANNOTATION_FILL) / 2 / TrackViewer.ZOOM_TO_ANNOTATION_FILL;
    this.zoomTo(annotation.start - margin, annotation.end + margin);
  }

  private renderPrimitive(
    container: Selection<SVGGElement, unknown, null, undefined>,
    primitive: DrawingPrimitive,
    xScale: ScaleLinear<number, number>,
    trackData: TrackData
  ): void {
    const trackHeight = this.getTrackHeight(trackData);
    
    let element: Selection<any, unknown, null, undefined>;

    switch (primitive.type) {
      case 'horizontal-line':
        element = this.renderHorizontalLine(container, primitive, xScale, trackHeight);
        break;
      case 'background':
        element = this.renderBackground(container, primitive, xScale, trackHeight);
        break;
      default:
        // Unknown primitive type, skip
        return;
    }

    // Apply styling (no event handlers for primitives)
    element.attr('class', `primitive ${primitive.class}`);
    
    // Apply custom styling if specified
    if (primitive.stroke) {
      element.style('stroke', primitive.stroke);
    } else if (primitive.type === 'horizontal-line') {
      // Default stroke for lines if not specified
      element.style('stroke', 'currentColor');
    }
    if (primitive.fill) {
      element.style('fill', primitive.fill);
    } else if (primitive.type === 'background') {
      // Default fill for backgrounds if not specified
      element.style('fill', 'none');
    }
    if (primitive.opacity !== undefined) {
      element.style('opacity', primitive.opacity);
    }
  }

  private renderHorizontalLine(
    container: Selection<SVGGElement, unknown, null, undefined>,
    primitive: DrawingPrimitive,
    xScale: ScaleLinear<number, number>,
    trackHeight: number
  ): Selection<SVGLineElement, unknown, null, undefined> {
    // If start is undefined, use the left edge of the chart
    // If end is undefined, use the right edge of the chart
    const range = xScale.range();
    
    let x1: number, x2: number;
    
    if (primitive.start !== undefined && primitive.end !== undefined) {
      // Both start and end defined - use them
      x1 = xScale(primitive.start);
      x2 = xScale(primitive.end);
    } else if (primitive.start !== undefined && primitive.end === undefined) {
      // Only start defined - from start to end of visible range
      x1 = xScale(primitive.start);
      x2 = range[1]; // Right edge of chart
    } else if (primitive.start === undefined && primitive.end !== undefined) {
      // Only end defined - from start of visible range to end
      x1 = range[0]; // Left edge of chart
      x2 = xScale(primitive.end);
    } else {
      // Neither start nor end defined - span entire visible range
      x1 = range[0]; // Left edge of chart
      x2 = range[1]; // Right edge of chart
    }

    const y = trackHeight - (primitive.fy !== undefined ? primitive.fy * trackHeight : trackHeight / 2); // Use custom fy or center of track

    // Round to nearest pixel to avoid anti-aliasing blur
    const roundedY = Math.round(y) + 0.5; // Add 0.5 for crisp 1px lines

    return container
      .append('line')
      .attr('x1', x1)
      .attr('x2', x2)
      .attr('y1', roundedY)
      .attr('y2', roundedY)
      .style('stroke-width', 1)
      .style('shape-rendering', 'crispEdges'); // Ensure crisp rendering
  }

  private renderBackground(
    container: Selection<SVGGElement, unknown, null, undefined>,
    primitive: DrawingPrimitive,
    xScale: ScaleLinear<number, number>,
    trackHeight: number
  ): Selection<SVGRectElement, unknown, null, undefined> {
    // If start is undefined, use the left edge of the chart
    // If end is undefined, use the right edge of the chart
    const range = xScale.range();
    
    let x1: number, x2: number;
    
    if (primitive.start !== undefined && primitive.end !== undefined) {
      // Both start and end defined - use them
      x1 = xScale(primitive.start);
      x2 = xScale(primitive.end);
    } else if (primitive.start !== undefined && primitive.end === undefined) {
      // Only start defined - from start to end of visible range
      x1 = xScale(primitive.start);
      x2 = range[1]; // Right edge of chart
    } else if (primitive.start === undefined && primitive.end !== undefined) {
      // Only end defined - from start of visible range to end
      x1 = range[0]; // Left edge of chart
      x2 = xScale(primitive.end);
    } else {
      // Neither start nor end defined - span entire visible range
      x1 = range[0]; // Left edge of chart
      x2 = range[1]; // Right edge of chart
    }

    return container
      .append('rect')
      .attr('x', x1)
      .attr('y', 0)
      .attr('width', x2 - x1)
      .attr('height', trackHeight);
  }

  private renderBox(
    container: Selection<SVGGElement, unknown, null, undefined>,
    x: number,
    y: number,
    width: number,
    height: number,
    corner_radius: number = 0
  ): Selection<SVGRectElement, unknown, null, undefined> {
    return container
      .append('rect')
      .attr('x', x)
      .attr('y', y - height / 2)
      .attr('width', width)
      .attr('height', height)
      .attr('rx', corner_radius)
      .attr('ry', corner_radius);
  }

  private renderArrow(
    container: Selection<SVGGElement, unknown, null, undefined>,
    x: number,
    y: number,
    width: number,
    height: number,
    direction: 'left' | 'right' | undefined
  ): Selection<SVGPathElement, unknown, null, undefined> {
    const arrowHeadWidth = Math.min(width * 0.2, height * 0.5, 8); // Limit arrow head size
    const bodyWidth = width - arrowHeadWidth;

    let pathData: string;

    const y1 = y - height / 2;
    const y2 = y + height / 2;
    if (direction === 'right') {
      // Arrow pointing right: rectangular body + triangular head
      pathData = `
        M ${x} ${y1}
        L ${x + bodyWidth} ${y1}
        L ${x + width} ${y}
        L ${x + bodyWidth} ${y2}
        L ${x} ${y2}
        Z
      `;
    } else if (direction === 'left') {
      // Arrow pointing left: triangular head + rectangular body
      pathData = `
        M ${x} ${y}
        L ${x + arrowHeadWidth} ${y1}
        L ${x + width} ${y1}
        L ${x + width} ${y2}
        L ${x + arrowHeadWidth} ${y2}
        Z
      `;
    } else {
      // No direction specified, render as elongated hexagon
      const indent = Math.min(width * 0.1, height * 0.3, 4);
      pathData = `
        M ${x + indent} ${y1}
        L ${x + width - indent} ${y1}
        L ${x + width} ${y}
        L ${x + width - indent} ${y2}
        L ${x + indent} ${y2}
        L ${x} ${y}
        Z
      `;
    }

    return container
      .append('path')
      .attr('d', pathData);
  }

  private renderCircle(
    container: Selection<SVGGElement, unknown, null, undefined>,
    x: number,
    y: number,
    height: number
  ): Selection<SVGCircleElement, unknown, null, undefined> {

    return container
      .append('circle')
      .attr('cx', x)
      .attr('cy', y)
      .attr('r', height / 2)
      .attr('class', 'annotation-marker');
  }

  private renderTriangle(
    container: Selection<SVGGElement, unknown, null, undefined>,
    x: number,
    y: number,
    height: number = 0.5
  ): Selection<SVGPolygonElement, unknown, null, undefined> {
    const baseWidth = height * 0.8;
    const points = [
      [x - baseWidth / 2, y + height],
      [x, y],
      [x + baseWidth / 2, y + height]
    ].map(p => p.join(',')).join(' ');

    return container
      .append('polygon')
      .attr('points', points)
      .attr('class', 'annotation-triangle');
  }

  private renderPin(
    container: Selection<SVGGElement, unknown, null, undefined>,
    x: number,
    y: number,
    height: number
  ): Selection<SVGGElement, unknown, null, undefined> {
    // Render a pin as a group containing a line and a circle
    const group = container
      .append('g')
      .attr('class', 'annotation-pin');

    group.append('line')
      .attr('x1', x)
      .attr('y1', y)
      .attr('x2', x)
      .attr('y2', y - height)
      .attr('stroke', 'black')
      .attr('class', 'annotation-pin-line');

    group.append('circle')
      .attr('cx', x)
      .attr('cy', y - height)
      .attr('r', 3)
      .attr('class', 'annotation-pin-head');

    return group;
  }

  private renderAnnotationLabel(
    container: Selection<SVGGElement, unknown, null, undefined>,
    annotation: AnnotationData,
    x: number,
    y: number,
    width: number,
    height: number
  ): void {
    // Check if label should be shown (default to 'hover')
    const showLabel = annotation.showLabel || 'hover';
    if (!annotation.label) {
      return;
    }

    // Make sure the group is displayed while rendering, so that the text can be measured.
    // The final visibility is set by applyLabelVisibility() in renderAllLabels().
    container.style('display', '');

    // Calculate label position (default to 'above')
    const labelPosition = annotation.labelPosition || 'above';
    let labelX: number;
    let labelY: number;
    let textAnchor: string = 'middle';

    if (annotation.type === 'circle' || annotation.type === 'triangle' || annotation.type === 'pin') {
      // For point annotations, position relative to the point
      labelX = x;
      if (labelPosition === 'above') {
        if (annotation.type === 'pin') {
          // Pins extend upward, so label should be above the pin head
          labelY = y - height - 8; // Above the pin head
        } else {
          labelY = y - height / 2 - 2; // Above the shape
        }
      } else {
        labelY = y; // Center of the shape
      }
    } else {
      // For box and arrow annotations, position relative to the shape
      labelX = x + width / 2; // Center horizontally
      if (labelPosition === 'above') {
        labelY = y - height / 2 - 8; // Above the shape
      } else {
        labelY = y; // Center of the shape
      }
    }

    // Create the text element first to measure its dimensions
    const labelElement = container
      .append('text')
      .attr('x', labelX)
      .attr('y', labelY)
      .attr('dy', '0.35em') // Vertically center text
      .attr('text-anchor', textAnchor)
      .attr('class', 'annotation-label')
      .attr('data-annotation-id', annotation.id)
      .attr('data-show-label', showLabel)
      .style('fill', 'currentColor') // Use currentColor to inherit from CSS color property
      .text(annotation.label);

    // Only add background for (possibly) hover labels - it will be shown/hidden based on hover state.
    // Centered labels don't need one, since the annotation's shape is behind them.
    if ((showLabel === 'hover' || showLabel === 'auto') && labelPosition !== 'center') {
      // Get text dimensions to create background
      const textNode = labelElement.node() as SVGTextElement;
      if (textNode && typeof textNode.getBBox === 'function') {
        try {
          const bbox = textNode.getBBox();
          const padding = 0;
          
          // Insert background rectangle before the text
          const background = container
            .insert('rect', 'text')
            .attr('x', bbox.x - padding)
            .attr('y', bbox.y - padding)
            .attr('width', bbox.width + padding * 2)
            .attr('height', bbox.height + padding * 2)
            .attr('rx', 2)
            .attr('ry', 2)
            .attr('class', 'annotation-label-background')
            .style('fill', 'white')
            .style('stroke', 'none') // Don't inherit stroke from annotation classes on the group
            .style('opacity', '0.8');
          
          // Initially hide the background - it will only show on actual hover
          background.style('display', 'none');
        } catch (error) {
          // If getBBox fails, continue without background
        }
      }
    }
  }

  // Mark each 'auto' label with whether it fits, i.e. doesn't overlap any other
  // 'always' or 'auto' label. Expects all label groups to be displayed.
  private updateAutoLabelFits<D extends { trackY: number }>(
    labelGroups: Selection<SVGGElement, D, SVGGElement, unknown>
  ): void {
    const minGap = 4; // Minimum horizontal space between labels (px)

    // Measure all labels first, before changing anything, to avoid repeated layout
    const boxes: Array<{ label: SVGTextElement; auto: boolean; x1: number; x2: number; y1: number; y2: number }> = [];
    labelGroups.each(function(d) {
      const label = this.querySelector<SVGTextElement>('.annotation-label');
      const showLabel = label?.getAttribute('data-show-label');
      if (!label || (showLabel !== 'always' && showLabel !== 'auto')) return;
      try {
        const bbox = label.getBBox();
        boxes.push({
          label,
          auto: showLabel === 'auto',
          x1: bbox.x,
          x2: bbox.x + bbox.width + minGap,
          y1: d.trackY + bbox.y,
          y2: d.trackY + bbox.y + bbox.height
        });
      } catch (error) {
        // getBBox not available (e.g. in tests): treat the label as fitting
        if (showLabel === 'auto') label.setAttribute('data-fits', 'true');
      }
    });

    // Sweep from left to right, comparing each label only to the ones that start before it ends
    boxes.sort((a, b) => a.x1 - b.x1);
    const overlapping = new Set<SVGTextElement>();
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length && boxes[j].x1 < boxes[i].x2; j++) {
        if (boxes[j].y1 < boxes[i].y2 && boxes[i].y1 < boxes[j].y2) {
          overlapping.add(boxes[i].label);
          overlapping.add(boxes[j].label);
        }
      }
    }

    for (const box of boxes) {
      if (box.auto) box.label.setAttribute('data-fits', String(!overlapping.has(box.label)));
    }
  }

  private renderAllLabels(
    labelsData: Array<{ annotation: AnnotationData; trackData: TrackData; x: number; y: number; width: number; height: number; trackY: number }>,
    xScale: ScaleLinear<number, number>
  ): void {
    // Create or select a labels layer that renders on top of everything
    let labelsLayer = this.clippedChart.select<SVGGElement>('.annotation-labels-layer');
    if (labelsLayer.empty()) {
      labelsLayer = this.clippedChart
        .append('g')
        .attr('class', 'annotation-labels-layer');
    }

    // Bind label data
    const labelGroups = labelsLayer
      .selectAll<SVGGElement, typeof labelsData[0]>('.annotation-label-group')
      .data(labelsData, (d) => d.annotation.id)
      .join(
        (enter) => enter.append('g'),
        (update) => update,
        (exit) => exit.remove()
      )
      .attr('class', (d) => `annotation-label-group ${d.annotation.classes.join(' ')}`)
      .attr('data-annotation-id', (d) => d.annotation.id)
      .attr('transform', (d) => `translate(0, ${d.trackY})`)
      .style('pointer-events', 'none');

    // Clear and re-render each label group
    const self = this;
    labelGroups.each(function(d) {
      const group = d3.select(this);
      group.selectAll('*').remove();
      self.renderAnnotationLabel(group, d.annotation, d.x, d.y, d.width, d.height);
    });

    this.updateAutoLabelFits(labelGroups);
    labelGroups.each((_, i, nodes) => this.applyLabelVisibility(d3.select(nodes[i])));
  }

  private showTooltip(event: MouseEvent, annotation: AnnotationData, trackData: TrackData): void {
    // Use custom tooltip content if provided, otherwise use default format
    const tooltipContent = annotation.tooltip !== undefined 
      ? annotation.tooltip
      : `<strong>${annotation.label}</strong><br/>Start: ${annotation.start}<br/>End: ${annotation.end}<br/>Track: ${trackData.label}`;

    this.tooltip
      .style('display', 'block')
      .style('left', `${event.pageX + 10}px`)
      .style('top', `${event.pageY - 10}px`)
      .html(tooltipContent);
  }

  private hideTooltip(): void {
    this.tooltip.style('display', 'none');
  }

  // Calculate required left margin based on track label lengths
  private calculateRequiredLeftMargin(): number {
    // If track labels are hidden, use the original minimal margin
    if (!this.showTrackLabels) {
      return this.originalLeftMargin;
    }

    if (this.data.tracks.length === 0) {
      return this.originalLeftMargin;
    }

    // Create a temporary text element to measure text width
    const tempText = this.svg
      .append('text')
      .attr('class', 'track-label') // Use same class as track labels for consistent measurement
      .style('visibility', 'hidden');

    let maxWidth = 0;
    this.data.tracks.forEach(track => {
      tempText.text(track.label);
      const textNode = tempText.node() as SVGTextElement;
      
      // Fallback for environments where getBBox is not available (like jsdom)
      if (textNode && typeof textNode.getBBox === 'function') {
        try {
          const bbox = textNode.getBBox();
          maxWidth = Math.max(maxWidth, bbox.width);
        } catch (error) {
          // Fallback to rough estimation: 8px per character
          maxWidth = Math.max(maxWidth, track.label.length * 8);
        }
      } else {
        // Fallback to rough estimation: 8px per character
        maxWidth = Math.max(maxWidth, track.label.length * 8);
      }
    });

    // Remove the temporary text element
    tempText.remove();

    // Add some padding (10px for spacing from edge + 10px for spacing from chart)
    const requiredMargin = Math.max(this.originalLeftMargin, maxWidth + 20);
    return requiredMargin;
  }

  private updateMarginAndLayout(): void {
    const newLeftMargin = this.calculateRequiredLeftMargin();
    
    // Only update if margin has changed significantly
    if (Math.abs(this.config.margin.left - newLeftMargin) > 5) {
      this.config.margin.left = newLeftMargin;
      this.updateChartWidth();
    }
  }

  // Public API methods
  public setData(data: TrackViewerData): void {
    this.data = {
      tracks: data.tracks,
      annotations: data.annotations,
      primitives: data.primitives || []
    };
    this.updateHeight();
    this.createTrackGroups();
    this.updateMarginAndLayout();
    this.drawTracks();
  }

  public addTrack(track: TrackData, annotations?: AnnotationData[], primitives?: DrawingPrimitive[]): void {
    this.data.tracks.push(track);
    if (annotations) {
      this.data.annotations.push(...annotations);
    }
    if (primitives) {
      if (!this.data.primitives) {
        this.data.primitives = [];
      }
      this.data.primitives.push(...primitives);
    }
    this.updateHeight();
    this.createTrackGroups();
    this.updateMarginAndLayout();
    this.drawTracks();
  }

  public removeTrack(trackId: string): void {
    this.data.tracks = this.data.tracks.filter(track => track.id !== trackId);
    this.data.annotations = this.data.annotations.filter(annotation => annotation.trackId !== trackId);
    this.data.primitives = (this.data.primitives || []).filter(primitive => primitive.trackId !== trackId);
    this.updateHeight();
    this.createTrackGroups();
    this.updateMarginAndLayout();
    this.drawTracks();
  }

  public addAnnotation(annotation: AnnotationData): void {
    this.data.annotations.push(annotation);
    this.drawTracks();
  }

  public removeAnnotation(annotationId: string): void {
    this.data.annotations = this.data.annotations.filter(annotation => annotation.id !== annotationId);
    this.drawTracks();
  }

  public addPrimitive(primitive: DrawingPrimitive): void {
    if (!this.data.primitives) {
      this.data.primitives = [];
    }
    this.data.primitives.push(primitive);
    this.drawTracks();
  }

  public removePrimitive(primitiveId: string): void {
    if (this.data.primitives) {
      this.data.primitives = this.data.primitives.filter(primitive => primitive.id !== primitiveId);
      this.drawTracks();
    }
  }

  public updateDomain(domain: [number, number]): void {
    this.config.domain = domain;
    this.x.domain(domain);
    this.drawTracks();
  }

  public zoomTo(start: number, end: number, duration: number = 750): void {
    const chartWidth = this.config.width - this.config.margin.left - this.config.margin.right;
    // Stay within the zoom extent (zooming to a tiny range would exceed it), centered on the range
    const [minScale, maxScale] = this.zoom.scaleExtent();
    const scale = Math.max(minScale, Math.min(maxScale, chartWidth / (this.x(end) - this.x(start))));
    const translate = chartWidth / 2 - (this.x(start) + this.x(end)) / 2 * scale;

    const transform = d3.zoomIdentity
      .translate(translate, 0)
      .scale(scale);

    this.applyTransform(transform, duration);
  }

  public resetZoom(duration: number = 750): void {
    this.applyTransform(d3.zoomIdentity, duration);
  }

  // Without a duration, the transform is applied immediately instead of in a transition
  private applyTransform(transform: ZoomTransform, duration: number): void {
    if (duration > 0) {
      // d3 zooms out, pans and zooms in along a smooth path. The default cubic easing peaks
      // at 3x the average speed mid-transition, which makes the panning in the middle rush;
      // sine easing peaks at ~1.6x, spreading the pan more evenly over the transition.
      this.svg
        .transition()
        .duration(duration)
        .ease(d3.easeSinInOut)
        .call(this.zoom.transform, transform);
    } else {
      this.svg.call(this.zoom.transform, transform);
    }
  }

  public destroy(): void {
    // Disconnect ResizeObserver if it was set up
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
    
    // Destroy context menu UI
    this.contextMenuController?.destroy();

    // Remove UI elements
    this.tooltip.remove();
    this.svg.remove();
  }

  public getConfig(): Required<TrackViewerConfig> {
    return { ...this.config };
  }

  public getData(): TrackViewerData {
    return {
      tracks: [...this.data.tracks],
      annotations: [...this.data.annotations],
      primitives: this.data.primitives ? [...this.data.primitives] : []
    };
  }

  public getCurrentDomain(): [number, number] {
    const xz = this.currentTransform.rescaleX(this.x);
    const range = xz.range();
    return [xz.invert(range[0]), xz.invert(range[1])];
  }

  public resize(): void {
    // Only resize if this instance was created with responsive width
    if (!this.isResponsiveWidth) {
      return;
    }

    const newWidth = this.calculateResponsiveWidth();
    
    // Only update if the width has changed significantly
    if (Math.abs(this.config.width - newWidth) > 10) {
      this.config.width = newWidth;
      this.svg.attr('width', newWidth);
      this.updateChartWidth();
    }
  }
}
