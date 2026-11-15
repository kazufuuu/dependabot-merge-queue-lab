// 動かしている Node の版が、正本（.tool-versions）と同じことを確かめる。
// 手元の版がずれていると、ここで落ちる。mise か asdf で、.tool-versions の版を入れる。
import { readFileSync } from "node:fs";
import { expect, test } from "vitest";

test("Node is the pinned version", () => {
  const pinned = readFileSync(new URL("../../.tool-versions", import.meta.url), "utf8").match(/^nodejs (\S+)$/m)[1];
  expect(process.versions.node).toBe(pinned);
});
