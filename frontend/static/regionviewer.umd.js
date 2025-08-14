
(function(l, r) { if (!l || l.getElementById('livereloadscript')) return; r = l.createElement('script'); r.async = 1; r.src = '//' + (self.location.host || 'localhost').split(':')[0] + ':35729/livereload.js?snipver=1'; r.id = 'livereloadscript'; l.getElementsByTagName('head')[0].appendChild(r) })(self.document);
(function (global, factory) {
    typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports, require('d3')) :
    typeof define === 'function' && define.amd ? define(['exports', 'd3'], factory) :
    (global = typeof globalThis !== 'undefined' ? globalThis : global || self, factory(global.BgcViewer = {}, global.d3));
})(this, (function (exports, d3) { 'use strict';

    function _interopNamespaceDefault(e) {
        var n = Object.create(null);
        if (e) {
            Object.keys(e).forEach(function (k) {
                if (k !== 'default') {
                    var d = Object.getOwnPropertyDescriptor(e, k);
                    Object.defineProperty(n, k, d.get ? d : {
                        enumerable: true,
                        get: function () { return e[k]; }
                    });
                }
            });
        }
        n.default = e;
        return Object.freeze(n);
    }

    var d3__namespace = /*#__PURE__*/_interopNamespaceDefault(d3);

    class RegionViewer {
        constructor(config) {
            this.data = { tracks: [], annotations: [] };
            // Set default configuration
            this.config = {
                container: config.container,
                width: config.width || 800,
                height: config.height || 300,
                margin: config.margin || { top: 20, right: 30, bottom: 20, left: 60 },
                rowHeight: config.rowHeight || 30,
                domain: config.domain || [0, 100],
                zoomExtent: config.zoomExtent || [0.5, 20],
                onAnnotationClick: config.onAnnotationClick || (() => { }),
                onAnnotationHover: config.onAnnotationHover || (() => { })
            };
            this.currentTransform = d3__namespace.zoomIdentity;
            this.initialize();
        }
        initialize() {
            // Get container element
            const containerElement = typeof this.config.container === 'string'
                ? document.querySelector(this.config.container)
                : this.config.container;
            if (!containerElement) {
                throw new Error('Container element not found');
            }
            // Create tooltip
            const body = document.body || document.documentElement;
            this.tooltip = d3__namespace.select(body)
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
            this.svg = d3__namespace.select(containerElement)
                .append('svg')
                .attr('width', this.config.width)
                .attr('height', this.config.height);
            // Create chart group
            this.chart = this.svg
                .append('g')
                .attr('transform', `translate(${this.config.margin.left},${this.config.margin.top})`);
            // Create clipping path to prevent annotations from overlapping labels
            const chartWidth = this.config.width - this.config.margin.left - this.config.margin.right;
            this.clipId = `clip-${Math.random().toString(36).substr(2, 9)}`;
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
            this.x = d3__namespace.scaleLinear()
                .domain(this.config.domain)
                .range([0, this.config.width - this.config.margin.left - this.config.margin.right]);
            // Initialize zoom behavior
            this.initializeZoom();
        }
        initializeZoom() {
            const chartWidth = this.config.width - this.config.margin.left - this.config.margin.right;
            const chartHeight = this.config.height - this.config.margin.top - this.config.margin.bottom;
            this.zoom = d3__namespace.zoom()
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
        updateHeight() {
            const newHeight = this.data.tracks.length * this.config.rowHeight + this.config.margin.top + this.config.margin.bottom;
            this.config.height = newHeight;
            this.svg.attr('height', newHeight);
            // Update x-axis position
            const chartHeight = this.data.tracks.length * this.config.rowHeight;
            this.xAxisGroup.attr('transform', `translate(0, ${chartHeight})`);
            // Update clipping path height
            this.svg.select('clipPath rect')
                .attr('height', chartHeight);
        }
        createTrackGroups() {
            this.trackGroups = this.clippedChart
                .selectAll('.track')
                .data(this.data.tracks, d => d.id)
                .join('g')
                .attr('class', 'track')
                .attr('transform', (_, i) => `translate(0, ${i * this.config.rowHeight})`);
            // Add track labels (these should be outside the clipped area)
            const labelGroups = this.chart
                .selectAll('.track-label-group')
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
            // Add annotation containers (inside clipped area)
            this.trackGroups
                .selectAll('.annotations')
                .data(d => [d])
                .join('g')
                .attr('class', 'annotations');
        }
        drawAnnotations() {
            const xz = this.currentTransform.rescaleX(this.x);
            // Update axis
            this.xAxisGroup.call(d3__namespace.axisBottom(xz));
            // Early return if no tracks have been created yet
            if (!this.trackGroups) {
                return;
            }
            // Update annotations for each track
            this.trackGroups.each((trackData, trackIndex, trackNodes) => {
                const trackGroup = d3__namespace.select(trackNodes[trackIndex]);
                const annotationsGroup = trackGroup.select('.annotations');
                // Get annotations for this track
                const trackAnnotations = this.data.annotations.filter(ann => ann.trackId === trackData.id);
                // Clear existing annotations
                annotationsGroup.selectAll('*').remove();
                // Render each annotation based on its type
                trackAnnotations.forEach(ann => {
                    this.renderAnnotation(annotationsGroup, ann, xz, trackData);
                });
            });
        }
        renderAnnotation(container, annotation, xScale, trackData) {
            const x = xScale(annotation.start);
            const width = Math.max(1, xScale(annotation.end) - xScale(annotation.start));
            const y = 5;
            const height = this.config.rowHeight - 10;
            let element;
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
                .attr('class', 'annotation')
                .style('fill', annotation.color || 'steelblue')
                .style('cursor', 'pointer')
                .on('mouseover', (event) => {
                element.style('fill', 'orange');
                this.showTooltip(event, annotation, trackData);
            })
                .on('mouseout', () => {
                element.style('fill', annotation.color || 'steelblue');
                this.hideTooltip();
            })
                .on('click', () => {
                // Convert to old format for callback compatibility
                const annotationCompat = {
                    start: annotation.start,
                    end: annotation.end,
                    label: annotation.label,
                    id: annotation.id
                };
                const trackCompat = {
                    track: trackData.label,
                    annotations: [], // Not used in callback
                    id: trackData.id
                };
                this.config.onAnnotationClick(annotationCompat, trackCompat);
            });
        }
        renderBox(container, x, y, width, height) {
            return container
                .append('rect')
                .attr('x', x)
                .attr('y', y)
                .attr('width', width)
                .attr('height', height)
                .attr('rx', 2) // Slightly rounded corners
                .attr('ry', 2);
        }
        renderArrow(container, x, y, width, height, direction) {
            const arrowHeadWidth = Math.min(width * 0.2, height * 0.5, 8); // Limit arrow head size
            const bodyWidth = width - (direction !== 'none' ? arrowHeadWidth : 0);
            let pathData;
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
            }
            else if (direction === 'left') {
                // Arrow pointing left: triangular head + rectangular body
                pathData = `
        M ${x} ${y + height * 0.5}
        L ${x + arrowHeadWidth} ${y}
        L ${x + width} ${y}
        L ${x + width} ${y + height}
        L ${x + arrowHeadWidth} ${y + height}
        Z
      `;
            }
            else {
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
        renderMarker(container, x, y, width, height) {
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
        showTooltip(event, annotation, trackData) {
            this.tooltip
                .style('display', 'block')
                .style('left', `${event.pageX + 10}px`)
                .style('top', `${event.pageY - 10}px`)
                .html(`<strong>${annotation.label}</strong><br/>Start: ${annotation.start}<br/>End: ${annotation.end}<br/>Track: ${trackData.label}`);
            // Convert to old format for callback compatibility
            const annotationCompat = {
                start: annotation.start,
                end: annotation.end,
                label: annotation.label,
                id: annotation.id
            };
            const trackCompat = {
                track: trackData.label,
                annotations: [], // Not used in callback
                id: trackData.id
            };
            this.config.onAnnotationHover(annotationCompat, trackCompat, event);
        }
        hideTooltip() {
            this.tooltip.style('display', 'none');
        }
        // Public API methods
        setData(data) {
            this.data = data;
            this.updateHeight();
            this.createTrackGroups();
            this.drawAnnotations();
        }
        // Backward compatibility method
        setTrackData(tracks) {
            // Convert old Track[] format to new RegionViewerData format
            const trackData = tracks.map(track => ({
                id: track.id || track.track,
                label: track.track
            }));
            const annotationData = tracks.flatMap(track => track.annotations.map(annotation => ({
                id: annotation.id || `${track.id || track.track}-${annotation.label}`,
                trackId: track.id || track.track,
                type: 'box',
                color: 'steelblue',
                label: annotation.label,
                start: annotation.start,
                end: annotation.end,
                direction: 'none'
            })));
            this.setData({ tracks: trackData, annotations: annotationData });
        }
        addTrack(track, annotations) {
            this.data.tracks.push(track);
            if (annotations) {
                this.data.annotations.push(...annotations);
            }
            this.updateHeight();
            this.createTrackGroups();
            this.drawAnnotations();
        }
        // Backward compatibility method
        addTrackLegacy(track) {
            const trackData = {
                id: track.id || track.track,
                label: track.track
            };
            const annotationData = track.annotations.map(annotation => ({
                id: annotation.id || `${track.id || track.track}-${annotation.label}`,
                trackId: track.id || track.track,
                type: 'box',
                color: 'steelblue',
                label: annotation.label,
                start: annotation.start,
                end: annotation.end,
                direction: 'none'
            }));
            this.addTrack(trackData, annotationData);
        }
        removeTrack(trackId) {
            this.data.tracks = this.data.tracks.filter(track => track.id !== trackId);
            this.data.annotations = this.data.annotations.filter(annotation => annotation.trackId !== trackId);
            this.updateHeight();
            this.createTrackGroups();
            this.drawAnnotations();
        }
        addAnnotation(annotation) {
            this.data.annotations.push(annotation);
            this.drawAnnotations();
        }
        removeAnnotation(annotationId) {
            this.data.annotations = this.data.annotations.filter(annotation => annotation.id !== annotationId);
            this.drawAnnotations();
        }
        updateDomain(domain) {
            this.config.domain = domain;
            this.x.domain(domain);
            this.drawAnnotations();
        }
        zoomTo(start, end) {
            const chartWidth = this.config.width - this.config.margin.left - this.config.margin.right;
            const scale = chartWidth / (this.x(end) - this.x(start));
            const translate = -this.x(start) * scale;
            const transform = d3__namespace.zoomIdentity
                .translate(translate, 0)
                .scale(scale);
            const zoomRect = this.svg.select('.zoom-overlay');
            zoomRect
                .transition()
                .duration(750)
                .call(this.zoom.transform, transform);
        }
        resetZoom() {
            const zoomRect = this.svg.select('.zoom-overlay');
            zoomRect
                .transition()
                .duration(750)
                .call(this.zoom.transform, d3__namespace.zoomIdentity);
        }
        destroy() {
            this.tooltip.remove();
            this.svg.remove();
        }
        getConfig() {
            return { ...this.config };
        }
        getData() {
            return {
                tracks: [...this.data.tracks],
                annotations: [...this.data.annotations]
            };
        }
        // Backward compatibility method
        getTrackData() {
            return this.data.tracks.map(track => {
                const annotations = this.data.annotations
                    .filter(annotation => annotation.trackId === track.id)
                    .map(annotation => ({
                    start: annotation.start,
                    end: annotation.end,
                    label: annotation.label,
                    id: annotation.id
                }));
                return {
                    track: track.label,
                    annotations,
                    id: track.id
                };
            });
        }
    }

    exports.RegionViewer = RegionViewer;

}));
//# sourceMappingURL=index.umd.js.map
