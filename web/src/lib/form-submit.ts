/**
 * Hotkey submission guard: Cmd/Ctrl+Enter and Cmd/Ctrl+S must not submit a
 * form whose submit button is disabled (e.g. a clean draft with
 * disabled={!dirty || isSaving}), because form.requestSubmit() fires the
 * submit event regardless of the button's disabled state.
 */
export function hotkeySubmitAllowed(
  form: Pick<HTMLFormElement, "dataset" | "querySelector"> | null,
): boolean {
  if (!form) return false;
  if (form.dataset.hotkeySubmitDisabled !== undefined) return false;
  const submit = form.querySelector<HTMLButtonElement>('button[type="submit"]');
  return submit === null || !submit.disabled;
}
