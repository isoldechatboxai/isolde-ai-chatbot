const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const frontend = path.resolve(__dirname, "..");
const read = (name) => fs.readFileSync(path.join(frontend, name), "utf8");
const jsFiles = fs.readdirSync(frontend).filter((name) => name.endsWith(".js"));

test("frontend has no persistent browser credential storage", () => {
  for (const name of [...jsFiles, "login.html"]) {
    const source = read(name);
    const persistentUses = source.match(/localStorage\.(?:getItem|setItem|removeItem)/g) || [];
    if (name === "script.js") {
      assert.equal(persistentUses.length, 1, "script only clears legacy localStorage values");
    } else {
      assert.equal(persistentUses.length, 0, `${name} must not use localStorage`);
    }
  }
});

test("tokens and identities use sessionStorage and logout clears them", () => {
  const script = read("script.js");
  const login = read("login.html");
  assert.match(script, /sessionStorage\.getItem\("access_token"\)/);
  assert.match(script, /sessionStorage\.removeItem\("access_token"\)/);
  assert.match(login, /sessionStorage\.setItem\('access_token'/);
  assert.match(login, /sessionStorage\.setItem\('user'/);
});

test("conversation contents are not browser-persisted", () => {
  const script = read("script.js");
  assert.doesNotMatch(script, /sessionStorage\.setItem\(STORAGE_KEYS\.CONVERSATIONS/);
  assert.doesNotMatch(script, /sessionStorage\.getItem\("isolde-conversations"/);
  assert.match(script, /authenticated backend[\s\S]*authoritative/i);
});

test("assistant markup is sanitized and source labels are rendered as text", () => {
  const script = read("script.js");
  assert.match(script, /sanitizeHtml\(marked\.parse/);
  assert.match(script, /!\["http:", "https:", "mailto:"\]\.includes\(url\.protocol\)/);
  assert.match(script, /item\.textContent = String\(source\)/);
  assert.doesNotMatch(script, /sourcesDiv\.innerHTML/);
});

test("web research uses the backend streaming contract, without simulated responses", () => {
  const script = read("script.js");
  assert.match(script, /fetch\("\/api\/chat\/stream"/);
  assert.match(script, /web_search: state\.webSearchEnabled/);
  assert.doesNotMatch(script, /fake (AI|research|citation|response)/i);
});

test("password flows use backend endpoints and do not persist reset tokens", () => {
  const login = read("login.html");
  const script = read("script.js");
  assert.match(login, /fetch\('\/api\/forgot-password'/);
  assert.match(login, /fetch\('\/api\/reset-password'/);
  assert.match(login, /history\.replaceState\(\{\}, '', '\/login\.html'\)/);
  assert.match(script, /"\/api\/settings\/password"/);
  assert.doesNotMatch(login, /sessionStorage\.setItem\(['"](?:reset|forgot|password)/i);
});
