import assert from "node:assert/strict";
import test from "node:test";

import {
  formatLocalizedError,
  formatLocalizedHint,
  hintActionMessage,
  isLocale,
  resolveInitialTheme,
  toggleThemeValue,
  translate,
  translateText,
} from "./translations";

test("locale validation accepts only supported values", () => {
  assert.equal(isLocale("en"), true);
  assert.equal(isLocale("zh-CN"), true);
  assert.equal(isLocale("zh"), false);
});

test("translations interpolate values and preserve product terms", () => {
  assert.equal(translate("zh-CN", "Missing {count}", { count: 3 }), "缺少 3 项");
  assert.equal(translate("zh-CN", "Generate SongSpec draft"), "生成 SongSpec 草稿");
  assert.equal(translate("en", "Create project"), "Create project");
});

test("system labels and generated patterns are localized", () => {
  assert.equal(translateText("zh-CN", "Verse 2"), "主歌 2");
  assert.equal(translateText("zh-CN", "Lyrics v4"), "歌词 v4");
  assert.equal(translateText("zh-CN", "revision.version_created"), "修改请求 · 已创建版本");
  assert.equal(translateText("zh-CN", "Using Arrangement v2."), "正在使用 编曲方案 v2。");
  assert.equal(translateText("en", "Verse 2"), "Verse 2");
});

test("Chinese API errors use a localized fallback and retain diagnostics", () => {
  const error = Object.assign(new Error("Internal English detail"), {
    status: 503,
    requestId: "request-123",
  });
  assert.equal(
    formatLocalizedError("zh-CN", error, "Failed to load workspace"),
    "加载工作台失败 (503) - 请求 ID：request-123",
  );
  assert.equal(
    formatLocalizedError("en", error, "Failed to load workspace"),
    "Internal English detail",
  );
});

test("error hints localize to the action button label", () => {
  assert.equal(hintActionMessage("check_prerequisites", "zh-CN"), "先生成缺失的资产");
  assert.equal(hintActionMessage("check_prerequisites", "en"), "Generate missing assets first");
  assert.equal(hintActionMessage("retry", "zh-CN"), "重试");
  assert.equal(hintActionMessage("approve_song_spec", "zh-CN"), "去确认 SongSpec");
  assert.equal(hintActionMessage(null, "en"), null);
  assert.equal(hintActionMessage("unknown_hint", "zh-CN"), "unknown_hint");
});

test("formatLocalizedHint reads the hint off error objects only", () => {
  assert.equal(formatLocalizedHint("zh-CN", { hint: "retry" }), "重试");
  assert.equal(formatLocalizedHint("en", { hint: "check_chord_symbol" }), "Check chord symbol or timing");
  assert.equal(formatLocalizedHint("zh-CN", { status: 500 }), null);
  assert.equal(formatLocalizedHint("zh-CN", new Error("x")), null);
});

test("resolveInitialTheme honors a valid cookie and falls back deliberately", () => {
  assert.equal(resolveInitialTheme("dark"), "dark");
  assert.equal(resolveInitialTheme(undefined), "light");
  assert.equal(resolveInitialTheme("garbage", "dark"), "dark");
  assert.equal(resolveInitialTheme(undefined, "dark"), "dark");
  assert.equal(resolveInitialTheme("light", "dark"), "light");
});

test("toggleThemeValue flips between the two themes", () => {
  assert.equal(toggleThemeValue("dark"), "light");
  assert.equal(toggleThemeValue("light"), "dark");
});
