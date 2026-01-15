# Records & Features API

Endpoints for accessing genomic records, regions, features, and annotations.

::: tip Prerequisites
You must first load an entry using `POST /api/load-entry` before using these endpoints.
:::

## Get Record Regions

Get all biosynthetic gene cluster regions for a specific record.

**Endpoint:** `GET /api/records/{record_id}/regions`

**Parameters:**
- `record_id` - The genomic record ID

**Response:**
```json
{
  "record_id": "NC_003888.3",
  "regions": [
    {
      "id": "region_1",
      "region_number": "1",
      "location": "[123456:234567](+)",
      "start": 123456,
      "end": 234567,
      "product": ["T1PKS"],
      "rules": ["PKS_AT"]
    }
  ]
}
```

**Example:**
```javascript
const response = await fetch('/api/records/NC_003888.3/regions');
const { regions } = await response.json();

regions.forEach(region => {
  console.log(`Region ${region.region_number}: ${region.product.join(', ')}`);
  console.log(`  Location: ${region.start}-${region.end}`);
});
```

---

## Get Region Features

Get all features within a specific region.

**Endpoint:** `GET /api/records/{record_id}/regions/{region_id}/features`

**Parameters:**
- `record_id` - The genomic record ID
- `region_id` - The region ID (e.g., `region_1`)

**Query Parameters:**
- `type` - Filter by feature type (optional)

**Response:**
```json
{
  "record_id": "NC_003888.3",
  "region_id": "region_1",
  "region_location": "[123456:234567](+)",
  "region_boundaries": {
    "start": 123456,
    "end": 234567
  },
  "feature_type": "CDS",
  "count": 42,
  "features": [
    {
      "type": "CDS",
      "location": "[123500:124500](+)",
      "qualifiers": {
        "locus_tag": ["SCO1234"],
        "gene": ["pksA"],
        "product": ["polyketide synthase"]
      }
    }
  ]
}
```

**Example:**
```javascript
// Get all CDS features in region 1
const response = await fetch('/api/records/NC_003888.3/regions/region_1/features?type=CDS');
const { features } = await response.json();

console.log(`Found ${features.length} CDS features`);
```

---

## Get Record Features

Get all features for a record (not limited to a specific region).

**Endpoint:** `GET /api/records/{record_id}/features`

**Parameters:**
- `record_id` - The genomic record ID

**Query Parameters:**
- `type` - Filter by feature type (optional)
- `limit` - Maximum number of features to return (optional)

**Response:**
```json
{
  "record_id": "NC_003888.3",
  "feature_type": "CDS",
  "count": 1247,
  "features": [...]
}
```

**Example:**
```javascript
// Get first 100 CDS features
const response = await fetch('/api/records/NC_003888.3/features?type=CDS&limit=100');
const { features, count } = await response.json();

console.log(`Showing 100 of ${count} CDS features`);
```

---

## Get MiBIG Entries

Get MiBIG database matches for a specific gene/locus tag.

**Endpoint:** `GET /api/records/{record_id}/mibig-entries/{locus_tag}`

**Parameters:**
- `record_id` - The genomic record ID
- `locus_tag` - The gene locus tag

**Query Parameters:**
- `region` - Region number (default: "1")

**Response:**
```json
{
  "record_id": "NC_003888.3",
  "locus_tag": "SCO1234",
  "region": "1",
  "count": 5,
  "entries": [
    {
      "mibig_protein": "AAA12345.1",
      "description": "polyketide synthase",
      "mibig_cluster": "BGC0001234",
      "rank": 1,
      "mibig_product": "actinorhodin",
      "percent_identity": 85.5,
      "blast_score": 1200,
      "percent_coverage": 95.0,
      "evalue": "0.0"
    }
  ]
}
```

**Example:**
```javascript
const response = await fetch('/api/records/NC_003888.3/mibig-entries/SCO1234?region=1');
const { entries } = await response.json();

entries.forEach(entry => {
  console.log(`${entry.mibig_cluster}: ${entry.description}`);
  console.log(`  Identity: ${entry.percent_identity}%`);
});
```

---

## Get TFBS Hits

Get transcription factor binding site predictions for a record.

**Endpoint:** `GET /api/records/{record_id}/tfbs-hits`

**Parameters:**
- `record_id` - The genomic record ID

**Query Parameters:**
- `region` - Region number (default: "1")

**Response:**
```json
{
  "record_id": "NC_003888.3",
  "region": "1",
  "count": 12,
  "hits": [
    {
      "name": "TetR_family",
      "start": 123456,
      "end": 123476,
      "score": 8.5,
      "strand": "+"
    }
  ]
}
```

**Example:**
```javascript
const response = await fetch('/api/records/NC_003888.3/tfbs-hits?region=1');
const { hits } = await response.json();

console.log(`Found ${hits.length} binding sites`);
```

---

## Get TTA Codons

Get TTA codon positions for a record (Streptomyces-specific).

**Endpoint:** `GET /api/records/{record_id}/tta-codons`

**Parameters:**
- `record_id` - The genomic record ID

**Response:**
```json
{
  "record_id": "NC_003888.3",
  "count": 8,
  "codons": [123456, 234567, 345678, ...]
}
```

**Example:**
```javascript
const response = await fetch('/api/records/NC_003888.3/tta-codons');
const { codons } = await response.json();

console.log(`TTA codons at positions: ${codons.join(', ')}`);
```

---

## Get Resistance Features

Get antibiotic resistance gene predictions for a record.

**Endpoint:** `GET /api/records/{record_id}/resistance`

**Parameters:**
- `record_id` - The genomic record ID

**Response:**
```json
{
  "record_id": "NC_003888.3",
  "count": 3,
  "features": [
    {
      "locus_tag": "SCO5678",
      "gene_id": "tetR",
      "description": "tetracycline resistance protein",
      "identity": 78.5,
      "coverage": 92.0,
      "evalue": "1e-45"
    }
  ]
}
```

**Example:**
```javascript
const response = await fetch('/api/records/NC_003888.3/resistance');
const { features } = await response.json();

features.forEach(f => {
  console.log(`${f.locus_tag}: ${f.description} (${f.identity}% identity)`);
});
```
