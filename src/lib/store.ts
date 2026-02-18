const store = { getState: () => ({}), setState: (_: Record<string, unknown>) => {} };
export default store;

// Key-value helpers used by SettingsContext
const _cache: Record<string, unknown> = {};

export async function get<T>(key: string, fallback: T): Promise<T> {
  if (key in _cache) return _cache[key] as T;
  return fallback;
}

export async function put<T>(key: string, value: T): Promise<void> {
  _cache[key] = value;
}
