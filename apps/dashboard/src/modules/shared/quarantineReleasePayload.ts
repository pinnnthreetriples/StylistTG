export function buildReleaseQuarantinePayload(reason: string, overrideGateBlock: boolean) {
  return { reason: reason || null, override_gate_block: overrideGateBlock }
}
