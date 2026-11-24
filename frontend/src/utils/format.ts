/** A length in base pairs as kilobases with one decimal, or '' when unknown. */
export const formatKilobases = (bp: number | null | undefined) =>
  bp == null ? '' : (bp / 1000).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })
