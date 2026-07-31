"use client";

/** Map of field-path -> message from an ApiRequestError.fields payload. */
export type FieldErrorMap = Record<string, string>;

/**
 * Return the error message for a single field, or null when clean.
 *
 * Usage inside a form component:
 * ```tsx
 * const fieldError = useFieldError(error, "tempo_bpm");
 * return <div><Input /><FieldError error={fieldError} /></div>;
 * ```
 */
export function useFieldError(
  error: unknown,
  fieldName: string,
): string | null {
  if (error == null || typeof error !== "object") return null;
  const err = error as { fields?: FieldErrorMap | null };
  return err.fields?.[fieldName] ?? null;
}
