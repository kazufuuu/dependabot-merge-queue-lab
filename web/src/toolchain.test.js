// 動かしている Node のバージョンが、管理場所（.node-version）と同じことを確かめる。
// 手元のバージョンがずれていると、ここで落ちる。.node-version のバージョンを入れる。
import { readFileSync } from "node:fs";
import { expect, test } from "vitest";

test("Node is the pinned version", () => {
  const pinned = readFileSync(new URL("../../.node-version", import.meta.url), "utf8").trim();
  expect(process.versions.node).toBe(pinned);
});
