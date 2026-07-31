"use client";

import { useEffect } from "react";

type HotkeyHandler = (event: KeyboardEvent) => void;

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

function isModifierPressed(event: KeyboardEvent): boolean {
  return event.metaKey || event.ctrlKey;
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
      if (event.key.toLowerCase() !== expectedKey) {
        return;
      }
      if (mod && !isModifierPressed(event)) {
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
      if (preventDefault) {
        event.preventDefault();
      }
      handler(event);
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [disabled, handler, key, mod, preventDefault, target]);
}
