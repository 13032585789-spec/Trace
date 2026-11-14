import type { Evidence } from '../types'

/** Nemotron second-opinion result for vision counts: green when both models agree, amber when they differ. */
export default function VerifyBadge({ ev }: { ev: Evidence }) {
  const v = ev.verified_by
  if (!v) return null
  if (v.nemotron_count == null)
    return <div className="badge grey">Nemotron 3.5 Super VL cross-check not run</div>
  if (v.agreement)
    return <div className="badge green">✓ NVIDIA Nemotron 3.5 Super VL cross-check: {String(ev.value)} = {v.nemotron_count} (verified)</div>
  return (
    <div className="badge amber">
      ⚠ Discrepancy: Gemini = {String(ev.value)}, Nemotron 3.5 Super VL = {v.nemotron_count} — human review required
    </div>
  )
}
