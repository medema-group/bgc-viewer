import * as d3 from 'd3';

export interface Annotation {
  start: number;
  end: number;
  label: string;
  id?: string;
}

export interface Track {
  track: string;
  annotations: Annotation[];
  id?: string;
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
  onAnnotationClick?: (annotation: Annotation, track: Track) => void;
  onAnnotationHover?: (annotation: Annotation, track: Track, event: MouseEvent) => void;
}

export class RegionViewer {
  private config: Required<RegionViewerConfig>;
  private svg!: d3.Selection<SVGSVGElement, unknown, null, undefined>;
  private chart!: d3.Selection<SVGGElement, unknown, null, undefined>;
  private xAxisGroup!: d3.Selection<SVGGElement, unknown, null, undefined>;
  private tooltip!: d3.Selection<HTMLDivElement, unknown, HTMLElement, any>;
  private x!: d3.ScaleLinear<number, number>;
  private currentTransform: d3.ZoomTransform;
  private zoom!: d3.ZoomBehavior<SVGRectElement, unknown>;
  private data: Track[] = [];
  private trackGroups!: d3.Selection<SVGGElement, Track, SVGGElement, unknown>;

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
      .style('z-index', '1000') as any;

    // Create SVG
    this.svg = d3.select(containerElement)
      .append('svg')
      .attr('width', this.config.width)
      .attr('height', this.config.height);

    // Create chart group
    this.chart = this.svg
      .append('g')
      .attr('transform', `translate(${this.config.margin.left},${this.config.margin.top})`);

    // Create x-axis group
    this.xAxisGroup = this.chart
      .append('g')
      .attr('class', 'x-axis');

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

    this.zoom = d3.zoom<SVGRectElement, unknown>()
      .scaleExtent(this.config.zoomExtent)
      .translateExtent([[0, 0], [chartWidth, chartHeight]])
      .extent([[0, 0], [chartWidth, chartHeight]])
      .on('zoom', (event) => {
        this.currentTransform = event.transform;
        this.drawAnnotations();
      });

    // Create zoom overlay
    this.svg
      .append('rect')
      .attr('class', 'zoom-overlay')
      .attr('width', chartWidth)
      .attr('height', chartHeight)
      .attr('transform', `translate(${this.config.margin.left},${this.config.margin.top})`)
      .style('fill', 'none')
      .style('pointer-events', 'all')
      .call(this.zoom);
  }

  private updateHeight(): void {
    const newHeight = this.data.length * this.config.rowHeight + this.config.margin.top + this.config.margin.bottom;
    this.config.height = newHeight;
    this.svg.attr('height', newHeight);

    // Update x-axis position
    const chartHeight = this.data.length * this.config.rowHeight;
    this.xAxisGroup.attr('transform', `translate(0, ${chartHeight})`);
  }

  private createTrackGroups(): void {
    this.trackGroups = this.chart
      .selectAll<SVGGElement, Track>('.track')
      .data(this.data, d => d.id || d.track)
      .join('g')
      .attr('class', 'track')
      .attr('transform', (_, i) => `translate(0, ${i * this.config.rowHeight})`);

    // Add track labels
    this.trackGroups
      .selectAll('.track-label')
      .data(d => [d])
      .join('text')
      .attr('class', 'track-label')
      .attr('x', -10)
      .attr('y', this.config.rowHeight / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', 'end')
      .style('font', '12px sans-serif')
      .text(d => d.track);

    // Add annotation containers
    this.trackGroups
      .selectAll('.annotations')
      .data(d => [d])
      .join('g')
      .attr('class', 'annotations');
  }

  private drawAnnotations(): void {
    const xz = this.currentTransform.rescaleX(this.x);

    // Update axis
    this.xAxisGroup.call(d3.axisBottom(xz));

    // Early return if no tracks have been created yet
    if (!this.trackGroups) {
      return;
    }

    // Update annotations for each track
    this.trackGroups.each((trackData, trackIndex, trackNodes) => {
      const trackGroup = d3.select(trackNodes[trackIndex]);
      const annotationsGroup = trackGroup.select('.annotations');

      const rects = annotationsGroup
        .selectAll<SVGRectElement, Annotation>('rect')
        .data(trackData.annotations, d => d.id || d.label);

      rects
        .join('rect')
        .attr('class', 'annotation')
        .attr('x', ann => xz(ann.start))
        .attr('y', 5)
        .attr('width', ann => Math.max(1, xz(ann.end) - xz(ann.start)))
        .attr('height', this.config.rowHeight - 10)
        .style('fill', 'steelblue')
        .style('cursor', 'pointer')
        .on('mouseover', (event, ann) => {
          d3.select(event.currentTarget).style('fill', 'orange');
          this.showTooltip(event, ann, trackData);
        })
        .on('mouseout', (event) => {
          d3.select(event.currentTarget).style('fill', 'steelblue');
          this.hideTooltip();
        })
        .on('click', (_, ann) => {
          this.config.onAnnotationClick(ann, trackData);
        });
    });
  }

  private showTooltip(event: MouseEvent, annotation: Annotation, track: Track): void {
    this.tooltip
      .style('display', 'block')
      .style('left', `${event.pageX + 10}px`)
      .style('top', `${event.pageY - 10}px`)
      .html(`<strong>${annotation.label}</strong><br/>Start: ${annotation.start}<br/>End: ${annotation.end}<br/>Track: ${track.track}`);

    this.config.onAnnotationHover(annotation, track, event);
  }

  private hideTooltip(): void {
    this.tooltip.style('display', 'none');
  }

  // Public API methods
  public setData(data: Track[]): void {
    this.data = data;
    this.updateHeight();
    this.createTrackGroups();
    this.drawAnnotations();
  }

  public addTrack(track: Track): void {
    this.data.push(track);
    this.setData(this.data);
  }

  public removeTrack(trackId: string): void {
    this.data = this.data.filter(track => (track.id || track.track) !== trackId);
    this.setData(this.data);
  }

  public updateDomain(domain: [number, number]): void {
    this.config.domain = domain;
    this.x.domain(domain);
    this.drawAnnotations();
  }

  public zoomTo(start: number, end: number): void {
    const chartWidth = this.config.width - this.config.margin.left - this.config.margin.right;
    const scale = chartWidth / (this.x(end) - this.x(start));
    const translate = -this.x(start) * scale;

    const transform = d3.zoomIdentity
      .translate(translate, 0)
      .scale(scale);

    const zoomRect = this.svg.select('.zoom-overlay') as d3.Selection<SVGRectElement, unknown, null, undefined>;
    zoomRect
      .transition()
      .duration(750)
      .call(this.zoom.transform, transform);
  }

  public resetZoom(): void {
    const zoomRect = this.svg.select('.zoom-overlay') as d3.Selection<SVGRectElement, unknown, null, undefined>;
    zoomRect
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

  public getData(): Track[] {
    return [...this.data];
  }
}
