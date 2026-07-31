import assert from "node:assert/strict";
import test from "node:test";

import { hotkeySubmitAllowed } from "./form-submit";

test("hotkeySubmitAllowed rejects a disabled submit button", () => {
  const form = {
    dataset: {},
    querySelector: () => ({ disabled: true }),
  } as unknown as HTMLFormElement;
  assert.equal(hotkeySubmitAllowed(form), false);
});

test("hotkeySubmitAllowed allows an enabled submit button", () => {
  const form = {
    dataset: {},
    querySelector: () => ({ disabled: false }),
  } as unknown as HTMLFormElement;
  assert.equal(hotkeySubmitAllowed(form), true);
});

test("hotkeySubmitAllowed allows forms without a submit button", () => {
  const form = {
    dataset: {},
    querySelector: () => null,
  } as unknown as HTMLFormElement;
  assert.equal(hotkeySubmitAllowed(form), true);
});

test("hotkeySubmitAllowed respects the data-hotkey-submit-disabled opt-out", () => {
  const form = {
    dataset: { hotkeySubmitDisabled: "" },
    querySelector: () => ({ disabled: false }),
  } as unknown as HTMLFormElement;
  assert.equal(hotkeySubmitAllowed(form), false);
});

test("hotkeySubmitAllowed rejects no form at all", () => {
  assert.equal(hotkeySubmitAllowed(null), false);
});
