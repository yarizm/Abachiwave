export class ApiRequestError extends Error {
  /** Stable machine-readable error code from X-Error-Code header (phase 0). */
  readonly errorCode: string | null;
  /** Actionable hint key from X-Error-Hint header (phase 0). */
  readonly hint: string | null;
  /** Field-level error map from 422 responses (field path -> message). */
  readonly fields: Record<string, string> | null;

  constructor(
    message: string,
    readonly status: number,
    readonly requestId: string | null,
    errorCode: string | null = null,
    hint: string | null = null,
    fields: Record<string, string> | null = null,
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.errorCode = errorCode;
    this.hint = hint;
    this.fields = fields;
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
  const { detail, errorCode: bodyCode, fields } = await readErrorBody(response);
  const headerCode = response.headers.get("X-Error-Code");
  const hint = response.headers.get("X-Error-Hint");
  const errorCode = headerCode ?? bodyCode;

  // Build a human-readable message, preferring the detail string when available.
  let message = `${label} request failed with ${response.status}`;
  if (typeof detail === "string" && detail.length > 0) {
    message = detail;
  } else if (fields && Object.keys(fields).length > 0) {
    const entry = Object.entries(fields)[0];
    message = `${entry[0]}: ${entry[1]}`;
  }
  if (errorCode) {
    message = `[${errorCode}] ${message}`;
  }

  throw new ApiRequestError(
    message,
    response.status,
    response.headers.get("X-Request-ID"),
    errorCode,
    hint,
    fields,
  );
}

async function readErrorBody(response: Response): Promise<{
  detail: string | null;
  errorCode: string | null;
  fields: Record<string, string> | null;
}> {
  try {
    const body = (await response.json()) as Record<string, unknown>;
    const detail = extractDetail(body?.detail);
    const errorCode =
      typeof body?.error_code === "string"
        ? (body.error_code as string)
        : (() => {
            const nested = body?.detail;
            return typeof nested === "object" &&
              nested !== null &&
              typeof (nested as Record<string, unknown>).error_code === "string"
              ? ((nested as Record<string, unknown>).error_code as string)
              : null;
          })();
    const fields =
      typeof body?.fields === "object" && body?.fields !== null
        ? (body.fields as Record<string, string>)
        : null;
    return { detail, errorCode, fields };
  } catch {
    return { detail: null, errorCode: null, fields: null };
  }
}

function extractDetail(raw: unknown): string | null {
  if (typeof raw === "string") {
    return raw;
  }
  // FastAPI default 422: [{loc: [...], msg: "...", type: "..."}, ...]
  if (Array.isArray(raw)) {
    return raw
      .map((item: { loc?: string[]; msg?: string }) => {
        const loc = item.loc?.filter((p) => p !== "body").join(".") ?? "";
        const label = loc ? `${loc}: ` : "";
        return `${label}${item.msg ?? ""}`;
      })
      .join("; ");
  }
  // Dict detail: {"message": "...", "missing": [...]}
  if (typeof raw === "object" && raw !== null) {
    const obj = raw as Record<string, unknown>;
    return typeof obj.message === "string" ? (obj.message as string) : null;
  }
  return null;
}
