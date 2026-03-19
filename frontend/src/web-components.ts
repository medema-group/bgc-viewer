/**
 * Web Components build entry point
 * Exports RegionViewer and RegionViewerContainer as Vue components (no shadow DOM)
 * Also exports TrackViewer class for direct use
 */

import RegionViewerContainerComponent from './components/RegionViewerContainer.vue'
import RegionViewerComponent from './components/RegionViewer.vue'

// Export the regular Vue components (recommended for Vue apps - no shadow DOM)
export { RegionViewerContainerComponent as RegionViewerContainer }
export { RegionViewerComponent as RegionViewer }

// Export data provider classes dynamically to avoid circular dependencies
export { BGCViewerAPIProvider } from './services/dataProviders/BGCViewerAPIProvider'
export { JSONFileProvider } from './services/dataProviders/JSONFileProvider'

// Export TrackViewer class and types
export { TrackViewer } from './TrackViewer'
export type { 
  TrackViewerConfig, 
  TrackData, 
  AnnotationData, 
  AnnotationType, 
  TrackViewerData,
  DrawingPrimitive,
  DrawingPrimitiveType
} from './TrackViewer'
