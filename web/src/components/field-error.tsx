import { useFieldError } from "@/lib/field-error";

/**
 * Inline field-level error text. Reuses the global `.error` class.
 * Renders nothing when the field is clean.
 */
export function FieldError({
  error,
  name,
}: {
  error: unknown;
  name: string;
}) {
  const message = useFieldError(error, name);
  if (!message) return null;
  return <span className="error compact-error">{message}</span>;
}
