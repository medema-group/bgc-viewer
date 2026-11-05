// Online databases that entries can be loaded from by ID. Each key is the value used for
// the data source selector, and also the path of the backend endpoint that fetches the entry.
export const EXTERNAL_SOURCES = {
  'antismash-db': {
    name: 'antiSMASH DB',
    homepage: 'https://antismash-db.secondarymetabolites.org/',
    idDescription: 'genome accession number',
    example: 'GCF_000725555.1',
    // Only allow characters that can appear in an accession, so the value can't alter the URL path
    pattern: /^[A-Za-z0-9_.-]+$/,
    urlParam: 'antismash_db'
  },
  mibig: {
    name: 'MIBiG',
    homepage: 'https://mibig.secondarymetabolites.org/',
    idDescription: 'versioned entry ID',
    example: 'BGC0002204.3',
    pattern: /^BGC\d{7}\.\d+$/,
    urlParam: 'mibig'
  }
}
