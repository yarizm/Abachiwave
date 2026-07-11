export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId: string | null,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function fetchJson<T>(url: string, label: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  await ensureApiResponse(response, label);
  return (await response.json()) as T;
}

export async function fetchBlob(url: string, label: string, init?: RequestInit): Promise<Blob> {
  const response = await fetch(url, init);
  await ensureApiResponse(response, label);
  return response.blob();
}

async function ensureApiResponse(response: Response, label: string): Promise<void> {
  if (response.ok) {
    return;
  }
  const detail = await readErrorDetail(response);
  const suffix = detail ? `: ${detail}` : "";
  throw new ApiRequestError(
    `${label} request failed with ${response.status}${suffix}`,
    response.status,
    response.headers.get("X-Request-ID"),
  );
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : null;
  } catch {
    return null;
  }
}
