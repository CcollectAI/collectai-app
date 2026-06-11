/**
 * recoveryState — tiny shared flag for the password-recovery deep-link flow.
 *
 * When the app opens via a `sparrow://reset-password` recovery link, AuthProvider
 * sets the session AND marks recovery pending. The root auth gate (app/_layout)
 * reads this so it routes the user to the reset-password screen instead of its
 * normal "signed-in -> tabs" redirect, which would otherwise race the recovery
 * link straight into the app. The reset-password screen clears it when done.
 *
 * Module-level singleton — the gate and the handler run in the same JS context.
 */
let pending = false;

export function setRecoveryPending(value: boolean): void {
  pending = value;
}

export function isRecoveryPending(): boolean {
  return pending;
}
