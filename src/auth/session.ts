export type SessionState = { ready: boolean; signedIn: boolean };
export function useSession(): SessionState {
  return { ready: true, signedIn: true };
}
