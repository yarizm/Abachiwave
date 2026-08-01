"use client";

import { useEffect } from "react";

type HotkeyHandler = (event: KeyboardEvent) => boolean;

type UseHotkeyOptions = {
  /** The key to match (e.g. "Enter", "s", "Escape"). Case-insensitive. */
  key: string;
  /** Require Cmd (macOS) / Ctrl (others). Defaults to false. */
  mod?: boolean;
  /** Call handler only when the keypress originates from within this element. */
  target?: HTMLElement | null;
  /** Disable the binding temporarily. Defaults to false. */
  disabled?: boolean;
  /** Prevent default browser behavior when the handler fires. Defaults to true. */
  preventDefault?: boolean;
};

export function matchesHotkey(
  event: Pick<KeyboardEvent, "key" | "metaKey" | "ctrlKey">,
  options: Pick<UseHotkeyOptions, "key" | "mod" | "disabled">,
): boolean {
  if (options.disabled || event.key.toLowerCase() !== options.key.toLowerCase()) {
    return false;
  }
  return !options.mod || event.metaKey || event.ctrlKey;
}

export function shouldPreventHotkeyDefault(
  handled: boolean,
  preventDefault = true,
): boolean {
  return handled && preventDefault;
}

function isInputElement(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable;
}

/**
 * Bind a keyboard shortcut scoped to a specific element (or the document when
 * no target is given). The handler fires only while focus is inside the target,
 * so global bindings don't hijack typing in unrelated inputs.
 */
export function useHotkey(options: UseHotkeyOptions, handler: HotkeyHandler) {
  const { key, mod = false, target, disabled = false, preventDefault = true } = options;

  useEffect(() => {
    if (disabled) {
      return;
    }
    const expectedKey = key.toLowerCase();

    function onKeyDown(event: KeyboardEvent) {
      if (!matchesHotkey(event, { key: expectedKey, mod, disabled })) {
        return;
      }
      if (target) {
        if (!target.contains(event.target as Node)) {
          return;
        }
      }
      // A plain (no-modifier) key must not fire while typing in a text field,
      // otherwise binding "s" would swallow normal text entry.
      if (!mod && isInputElement(event.target)) {
        return;
      }
      const handled = handler(event);
      if (shouldPreventHotkeyDefault(handled, preventDefault)) {
        event.preventDefault();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [disabled, handler, key, mod, preventDefault, target]);
}
