import * as d3 from 'd3';

export type TrackData = {
  id: string;
  label: string;
}

export type AnnotationType = 'arrow' | 'box' | 'marker';

export type AnnotationData = {
  id: string;
  trackId: string;
  type: AnnotationType;
  class: string;
  label: string;
  start: number;
  end: number;
  heightFraction?: number;
  direction: 'left' | 'right' | 'none';
}

export type DrawingPrimitiveType = 'horizontal-line';

export type DrawingPrimitive = {
  id: string;
  trackId: string;
  type: DrawingPrimitiveType;
  class: string;
  start?: number;
  end?: number;
  y?: number; // Optional vertical position override (relative to track)
}

export type RegionViewerData = {
  tracks: TrackData[];
  annotations: AnnotationData[];
  primitives?: DrawingPrimitive[];
}

export interface RegionViewerConfig {
  container: string | HTMLElement;
  width?: number;
  height?: number;
  margin?: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
  rowHeight?: number;
  domain?: [number, number];
  zoomExtent?: [number, number];
  onAnnotationClick?: (annotation: AnnotationData, track: TrackData) => void;
  onAnnotationHover?: (annotation: AnnotationData, track: TrackData, event: MouseEvent) => void;
}


export class RegionViewer {
  private config: Required<RegionViewerConfig>;
  private svg!: d3.Selection<SVGSVGElement, unknown, null, undefined>;
  private chart!: d3.Selection<SVGGElement, unknown, null, undefined>;
  private clippedChart!: d3.Selection<SVGGElement, unknown, null, undefined>;
  private xAxisGroup!: d3.Selection<SVGGElement, unknown, null, undefined>;
  private tooltip!: d3.Selection<HTMLDivElement, unknown, null, undefined>;
  private x!: d3.ScaleLinear<number, number>;
  private currentTransform: d3.ZoomTransform;
  private zoom!: d3.ZoomBehavior<any, unknown>;
  private data: RegionViewerData = { tracks: [], annotations: [], primitives: [] };
  private trackGroups!: d3.Selection<SVGGElement, TrackData, SVGGElement, unknown>;
  private clipId!: string;
  private originalLeftMargin: number; // Store original left margin

  constructor(config: RegionViewerConfig) {
    // Set default configuration
    this.config = {
      container: config.container,
      width: config.width || 800,
      height: config.height || 300,
      margin: config.margin || { top: 20, right: 30, bottom: 20, left: 60 },
      rowHeight: config.rowHeight || 30,
      domain: config.domain || [0, 100],
      zoomExtent: config.zoomExtent || [0.5, 20],
      onAnnotationClick: config.onAnnotationClick || (() => {}),
      onAnnotationHover: config.onAnnotationHover || (() => {})
    };

    // Store the original left margin as minimum
    this.originalLeftMargin = this.config.margin.left;

    this.currentTransform = d3.zoomIdentity;
    this.initialize();
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
      .attr('class', 'region-viewer-tooltip')
      .style('position', 'absolute')
      .style('background', 'white')
      .style('border', '1px solid #ccc')
      .style('padding', '4px 8px')
      .style('font-size', '12px')
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
      .attr('y', 0)
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
  }

  private initializeZoom(): void {
    const chartWidth = this.config.width - this.config.margin.left - this.config.margin.right;
    const chartHeight = this.config.height - this.config.margin.top - this.config.margin.bottom;

    this.zoom = d3.zoom<any, unknown>()
      .scaleExtent(this.config.zoomExtent)
      .translateExtent([[0, 0], [chartWidth, chartHeight]])
      .extent([[0, 0], [chartWidth, chartHeight]])
      .on('zoom', (event) => {
        this.currentTransform = event.transform;
        this.drawTracks();
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
      .style('fill', 'transparent')
      .style('pointer-events', 'all')
      .style('cursor', 'grab')
      .on('mousedown', function() {
        d3.select(this).style('cursor', 'grabbing');
      })
      .on('mouseup', function() {
        d3.select(this).style('cursor', 'grab');
      });
  }

  private updateHeight(): void {
    const newHeight = this.data.tracks.length * this.config.rowHeight + this.config.margin.top + this.config.margin.bottom;
    this.config.height = newHeight;
    this.svg.attr('height', newHeight);

    // Update x-axis position
    const chartHeight = this.data.tracks.length * this.config.rowHeight;
    this.xAxisGroup.attr('transform', `translate(0, ${chartHeight})`);

    // Update clipping path height
    this.svg.select('clipPath rect')
      .attr('height', chartHeight);

    // Update chart background height
    this.clippedChart.select('.chart-background')
      .attr('height', chartHeight);
  }

  private createTrackGroups(): void {
    this.trackGroups = this.clippedChart
      .selectAll<SVGGElement, TrackData>('.track')
      .data(this.data.tracks, d => d.id)
      .join('g')
      .attr('class', 'track')
      .attr('transform', (_, i) => `translate(0, ${i * this.config.rowHeight})`);

    // Add track labels (these should be outside the clipped area)
    const labelGroups = this.chart
      .selectAll<SVGGElement, TrackData>('.track-label-group')
      .data(this.data.tracks, d => d.id)
      .join('g')
      .attr('class', 'track-label-group')
      .attr('transform', (_, i) => `translate(0, ${i * this.config.rowHeight})`);

    labelGroups
      .selectAll('.track-label')
      .data(d => [d])
      .join('text')
      .attr('class', 'track-label')
      .attr('x', -10)
      .attr('y', this.config.rowHeight / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .style('font', '12px sans-serif')
      .text(d => d.label);

    // Add primitives containers first (inside clipped area, will render behind annotations)
    this.trackGroups
      .selectAll('.primitives')
      .data(d => [d])
      .join('g')
      .attr('class', 'primitives');

    // Add annotation containers after (inside clipped area, will render in front of primitives)
    this.trackGroups
      .selectAll('.annotations')
      .data(d => [d])
      .join('g')
      .attr('class', 'annotations');
  }

  private drawTracks(): void {
    const xz = this.currentTransform.rescaleX(this.x);

    // Update axis
    this.xAxisGroup.call(d3.axisBottom(xz));

    // Early return if no tracks have been created yet
    if (!this.trackGroups) {
      return;
    }

    // Update annotations and primitives for each track
    this.trackGroups.each((trackData, trackIndex, trackNodes) => {
      const trackGroup = d3.select(trackNodes[trackIndex]);
      const annotationsGroup = trackGroup.select<SVGGElement>('.annotations');
      const primitivesGroup = trackGroup.select<SVGGElement>('.primitives');

      // Get annotations for this track
      const trackAnnotations = this.data.annotations.filter(ann => ann.trackId === trackData.id);
      
      // Get primitives for this track
      const trackPrimitives = (this.data.primitives || []).filter(prim => prim.trackId === trackData.id);

      // Clear existing primitives and annotations
      primitivesGroup.selectAll('*').remove();
      annotationsGroup.selectAll('*').remove();

      // Render primitives first (so they appear behind annotations)
      trackPrimitives.forEach(primitive => {
        this.renderPrimitive(primitivesGroup, primitive, xz, trackData);
      });

      // Render annotations on top
      trackAnnotations.forEach(ann => {
        this.renderAnnotation(annotationsGroup, ann, xz, trackData);
      });
    });
  }

  private renderAnnotation(
    container: d3.Selection<SVGGElement, unknown, null, undefined>,
    annotation: AnnotationData,
    xScale: d3.ScaleLinear<number, number>,
    trackData: TrackData
  ): void {
    const x = xScale(annotation.start);
    const width = Math.max(1, xScale(annotation.end) - xScale(annotation.start));
    
    // Calculate height based on heightFraction if provided, otherwise use default
    const defaultHeight = this.config.rowHeight - 10;
    const height = annotation.heightFraction !== undefined 
      ? this.config.rowHeight * annotation.heightFraction
      : defaultHeight;
    
    // Center the annotation vertically in the track
    const y = (this.config.rowHeight - height) / 2;

    let element: d3.Selection<any, unknown, null, undefined>;

    switch (annotation.type) {
      case 'arrow':
        element = this.renderArrow(container, x, y, width, height, annotation.direction);
        break;
      case 'marker':
        element = this.renderMarker(container, x, y, width, height);
        break;
      case 'box':
      default:
        element = this.renderBox(container, x, y, width, height);
        break;
    }

    // Apply common styling and event handlers
    element
      .attr('class', `annotation ${annotation.class}`)
      .style('cursor', 'pointer')
      .style('pointer-events', 'all') // Ensure annotations can receive mouse events
      .on('mouseover', (event: any) => {
        element.classed('hovered', true);
        this.showTooltip(event, annotation, trackData);
      })
      .on('mouseout', () => {
        element.classed('hovered', false);
        this.hideTooltip();
      })
      .on('click', () => {
        this.config.onAnnotationClick(annotation, trackData);
      });
  }

  private renderPrimitive(
    container: d3.Selection<SVGGElement, unknown, null, undefined>,
    primitive: DrawingPrimitive,
    xScale: d3.ScaleLinear<number, number>,
    _trackData: TrackData
  ): void {
    const trackHeight = this.config.rowHeight;
    
    let element: d3.Selection<any, unknown, null, undefined>;

    switch (primitive.type) {
      case 'horizontal-line':
        element = this.renderHorizontalLine(container, primitive, xScale, trackHeight);
        break;
      default:
        // Unknown primitive type, skip
        return;
    }

    // Apply styling (no event handlers for primitives)
    element.attr('class', `primitive ${primitive.class}`);
  }

  private renderHorizontalLine(
    container: d3.Selection<SVGGElement, unknown, null, undefined>,
    primitive: DrawingPrimitive,
    xScale: d3.ScaleLinear<number, number>,
    trackHeight: number
  ): d3.Selection<SVGLineElement, unknown, null, undefined> {
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
    
    const y = primitive.y !== undefined ? primitive.y : trackHeight / 2; // Use custom y or center of track

    // Round to nearest pixel to avoid anti-aliasing blur
    const roundedY = Math.round(y) + 0.5; // Add 0.5 for crisp 1px lines

    return container
      .append('line')
      .attr('x1', x1)
      .attr('x2', x2)
      .attr('y1', roundedY)
      .attr('y2', roundedY)
      .style('stroke', 'currentColor')
      .style('stroke-width', 1)
      .style('shape-rendering', 'crispEdges'); // Ensure crisp rendering
  }

  private renderBox(
    container: d3.Selection<SVGGElement, unknown, null, undefined>,
    x: number,
    y: number,
    width: number,
    height: number
  ): d3.Selection<SVGRectElement, unknown, null, undefined> {
    return container
      .append('rect')
      .attr('x', x)
      .attr('y', y)
      .attr('width', width)
      .attr('height', height)
      .attr('rx', 2) // Slightly rounded corners
      .attr('ry', 2);
  }

  private renderArrow(
    container: d3.Selection<SVGGElement, unknown, null, undefined>,
    x: number,
    y: number,
    width: number,
    height: number,
    direction: 'left' | 'right' | 'none'
  ): d3.Selection<SVGPathElement, unknown, null, undefined> {
    const arrowHeadWidth = Math.min(width * 0.2, height * 0.5, 8); // Limit arrow head size
    const bodyWidth = width - (direction !== 'none' ? arrowHeadWidth : 0);
    
    let pathData: string;
    
    if (direction === 'right') {
      // Arrow pointing right: rectangular body + triangular head
      pathData = `
        M ${x} ${y}
        L ${x + bodyWidth} ${y}
        L ${x + width} ${y + height * 0.5}
        L ${x + bodyWidth} ${y + height}
        L ${x} ${y + height}
        Z
      `;
    } else if (direction === 'left') {
      // Arrow pointing left: triangular head + rectangular body
      pathData = `
        M ${x} ${y + height * 0.5}
        L ${x + arrowHeadWidth} ${y}
        L ${x + width} ${y}
        L ${x + width} ${y + height}
        L ${x + arrowHeadWidth} ${y + height}
        Z
      `;
    } else {
      // No direction specified, render as elongated hexagon
      const indent = Math.min(width * 0.1, height * 0.3, 4);
      pathData = `
        M ${x + indent} ${y}
        L ${x + width - indent} ${y}
        L ${x + width} ${y + height * 0.5}
        L ${x + width - indent} ${y + height}
        L ${x + indent} ${y + height}
        L ${x} ${y + height * 0.5}
        Z
      `;
    }

    return container
      .append('path')
      .attr('d', pathData);
  }

  private renderMarker(
    container: d3.Selection<SVGGElement, unknown, null, undefined>,
    x: number,
    y: number,
    width: number,
    height: number
  ): d3.Selection<SVGCircleElement, unknown, null, undefined> {
    // Render marker as a circle
    const centerX = x + width / 2;
    const centerY = y + height / 2;
    const radius = Math.min(width, height) / 2;
    
    return container
      .append('circle')
      .attr('cx', centerX)
      .attr('cy', centerY)
      .attr('r', radius)
      .attr('class', 'annotation-marker');
  }

  private showTooltip(event: MouseEvent, annotation: AnnotationData, trackData: TrackData): void {
    this.tooltip
      .style('display', 'block')
      .style('left', `${event.pageX + 10}px`)
      .style('top', `${event.pageY - 10}px`)
      .html(`<strong>${annotation.label}</strong><br/>Start: ${annotation.start}<br/>End: ${annotation.end}<br/>Track: ${trackData.label}`);

    this.config.onAnnotationHover(annotation, trackData, event);
  }

  private hideTooltip(): void {
    this.tooltip.style('display', 'none');
  }

  // Calculate required left margin based on track label lengths
  private calculateRequiredLeftMargin(): number {
    if (this.data.tracks.length === 0) {
      return this.originalLeftMargin;
    }

    // Create a temporary text element to measure text width
    const tempText = this.svg
      .append('text')
      .style('font', '12px sans-serif')
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
      
      // Update chart transform
      this.chart.attr('transform', `translate(${this.config.margin.left},${this.config.margin.top})`);
      
      // Update x scale range
      this.x.range([0, this.config.width - this.config.margin.left - this.config.margin.right]);
      
      // Update clipping path width
      const chartWidth = this.config.width - this.config.margin.left - this.config.margin.right;
      this.svg.select('clipPath rect').attr('width', chartWidth);
      
      // Update chart background width
      this.clippedChart.select('.chart-background')
        .attr('width', chartWidth);
    }
  }

  // Public API methods
  public setData(data: RegionViewerData): void {
    this.data = {
      tracks: data.tracks,
      annotations: data.annotations,
      primitives: data.primitives || []
    };
    this.updateMarginAndLayout();
    this.updateHeight();
    this.createTrackGroups();
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
    this.updateMarginAndLayout();
    this.updateHeight();
    this.createTrackGroups();
    this.drawTracks();
  }

  public removeTrack(trackId: string): void {
    this.data.tracks = this.data.tracks.filter(track => track.id !== trackId);
    this.data.annotations = this.data.annotations.filter(annotation => annotation.trackId !== trackId);
    this.data.primitives = (this.data.primitives || []).filter(primitive => primitive.trackId !== trackId);
    this.updateMarginAndLayout();
    this.updateHeight();
    this.createTrackGroups();
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

  public zoomTo(start: number, end: number): void {
    const chartWidth = this.config.width - this.config.margin.left - this.config.margin.right;
    const scale = chartWidth / (this.x(end) - this.x(start));
    const translate = -this.x(start) * scale;

    const transform = d3.zoomIdentity
      .translate(translate, 0)
      .scale(scale);

    this.svg
      .transition()
      .duration(750)
      .call(this.zoom.transform, transform);
  }

  public resetZoom(): void {
    this.svg
      .transition()
      .duration(750)
      .call(this.zoom.transform, d3.zoomIdentity);
  }

  public destroy(): void {
    this.tooltip.remove();
    this.svg.remove();
  }

  public getConfig(): Required<RegionViewerConfig> {
    return { ...this.config };
  }

  public getData(): RegionViewerData {
    return {
      tracks: [...this.data.tracks],
      annotations: [...this.data.annotations],
      primitives: this.data.primitives ? [...this.data.primitives] : []
    };
  }
}
