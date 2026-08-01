import assert from "node:assert/strict";
import test from "node:test";

import { matchesHotkey, shouldPreventHotkeyDefault } from "./use-hotkey";

function event(key: string, mod = false) {
  return { key, metaKey: mod, ctrlKey: false };
}

test("useHotkey matching: plain key matches without modifier", () => {
  assert.equal(matchesHotkey(event("s"), { key: "s", mod: false, disabled: false }), true);
});

test("useHotkey matching: mod key requires meta/ctrl", () => {
  assert.equal(matchesHotkey(event("Enter"), { key: "Enter", mod: true, disabled: false }), false);
  assert.equal(matchesHotkey(event("Enter", true), { key: "Enter", mod: true, disabled: false }), true);
});

test("useHotkey matching: key is case-insensitive", () => {
  assert.equal(matchesHotkey(event("S"), { key: "s", mod: false, disabled: false }), true);
  assert.equal(matchesHotkey(event("s"), { key: "S", mod: false, disabled: false }), true);
});

test("useHotkey matching: disabled never matches", () => {
  assert.equal(matchesHotkey(event("s"), { key: "s", mod: false, disabled: true }), false);
});

test("useHotkey matching: unrelated key does not match", () => {
  assert.equal(matchesHotkey(event("a"), { key: "s", mod: false, disabled: false }), false);
});

test("useHotkey prevents browser defaults only when the handler handled the shortcut", () => {
  assert.equal(shouldPreventHotkeyDefault(true), true);
  assert.equal(shouldPreventHotkeyDefault(false), false);
  assert.equal(shouldPreventHotkeyDefault(true, false), false);
});
