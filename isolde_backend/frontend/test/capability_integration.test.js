const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const script = fs.readFileSync(path.resolve(__dirname, "..", "script.js"), "utf8");

test("main app consumes backend capability truth and uses automatic intent routing", () => {
  assert.match(script, /fetch\("\/api\/capabilities"/);
  assert.match(script, /state\.capabilities\.research !== "AVAILABLE"/);
  assert.match(script, /research_mode: state\.webSearchEnabled \? "required" : "auto"/);
  assert.match(script, /Web: Unavailable/);
});
