// Dataset attribution shown under every drawing. Licence texts must be checked against the
// LICENSE files shipped in the Stoa dataset before adding them here; until then only the source is named.
const SOURCES: Record<string, string> = {
  cubicasa5k: 'CubiCasa5k',
  swiss_dwellings: 'Swiss Dwellings',
  ifc_models: 'IFC sample models',
  ifc_bench: 'IFC bench',
  opening_design: 'Opening Design',
}
const LICENSES: Record<string, string> = {}

export default function LicenseBadge({ path }: { path: string }) {
  const key = Object.keys(SOURCES).find((k) => path.includes(`/${k}/`) || path.startsWith(`${k}/`))
  if (!key) return null
  return (
    <div className="license">
      Source: {SOURCES[key]}{LICENSES[key] ? ` (${LICENSES[key]})` : ''} · via Stoa Junction 2026 dataset
    </div>
  )
}
