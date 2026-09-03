import { PfamColorMap } from './types'

/**
 * Parse PFAM color map from CSV text
 * @param csvText - CSV text with format "id,color" (with header line)
 * @returns Color map object
 */
export function parsePfamColorMapCSV(csvText: string): PfamColorMap {
  const lines = csvText.split('\n')
  const colorMap: PfamColorMap = {}
  
  // Skip header line and process each color mapping
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim()
    if (line) {
      const [id, color] = line.split(',')
      if (id && color) {
        colorMap[id] = color
      }
    }
  }
  
  return colorMap
}

/**
 * Fetch and parse PFAM color map from a URL
 * @param url - URL to the CSV file (default: '/domain-colors.csv')
 * @returns Color map object
 */
export async function fetchPfamColorMap(url: string = '/domain-colors.csv'): Promise<PfamColorMap> {
  try {
    const response = await fetch(url)
    if (!response.ok) {
      console.warn(`Failed to load PFAM color mapping from ${url}: ${response.status} ${response.statusText}`)
      return {}
    }
    const csvText = await response.text()
    return parsePfamColorMapCSV(csvText)
  } catch (err) {
    console.warn(`Failed to load PFAM color mapping from ${url}:`, err)
    return {}
  }
}
