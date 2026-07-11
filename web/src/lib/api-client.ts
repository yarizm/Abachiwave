export function ensureOk(response: Response, label: string): void {
  if (!response.ok) {
    throw new Error(`${label} request failed with ${response.status}`);
  }
}

export async function fetchJson<T>(url: string, label: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  ensureOk(response, label);
  return (await response.json()) as T;
}
