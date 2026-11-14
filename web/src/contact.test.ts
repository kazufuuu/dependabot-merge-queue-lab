import { describe, expect, it } from "vitest";
import { fieldErrors, lastContactedLabel, parseContact } from "./contact";

describe("parseContact", () => {
  it("名前の前後の空白を落とす", () => {
    expect(parseContact({ name: "  Aya ", email: "aya@example.com" }).name).toBe("Aya");
  });

  it("不正な項目の名前を返す", () => {
    expect(fieldErrors({ name: " ", email: "aya@", lastContactedAt: "2026-01-10" })).toEqual([
      "name",
      "email",
      "lastContactedAt",
    ]);
  });
});

describe("lastContactedLabel", () => {
  const now = new Date("2026-01-10T12:00:00Z");
  const base = { name: "Aya", email: "aya@example.com" };

  it("連絡していなければ未連絡", () => {
    expect(lastContactedLabel(base, now)).toBe("未連絡");
  });

  it("7 日未満は日数で示す", () => {
    expect(lastContactedLabel({ ...base, lastContactedAt: "2026-01-10T01:00:00Z" }, now)).toBe("今日");
    expect(lastContactedLabel({ ...base, lastContactedAt: "2026-01-07T12:00:00Z" }, now)).toBe("3 日前");
  });

  it("7 日以上は日付で示す", () => {
    expect(lastContactedLabel({ ...base, lastContactedAt: "2025-12-01T12:00:00Z" }, now)).toBe("2025-12-01");
  });
});
