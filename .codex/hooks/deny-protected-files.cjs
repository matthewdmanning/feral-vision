const fs = require("fs");
const path = require("path");

const input = JSON.parse(fs.readFileSync(0, "utf8"));
const listPath = path.join(
  input.cwd || process.cwd(),
  ".claude",
  "protected-files.txt",
);

const normalize = (text) => text.replace(/\\/g, "/").toLowerCase();

const protectedNames = fs
  .readFileSync(listPath, "utf8")
  .split(/\r?\n/)
  .map((line) => line.trim())
  .filter((line) => line && !line.startsWith("#"))
  .map((line) => normalize(path.basename(line)));

const request = normalize(JSON.stringify(input.tool_input ?? {}));
const hit = protectedNames.find((name) => request.includes(name));

if (hit) {
  console.error(`Blocked: ${input.tool_name} refers to protected file "${hit}".`);
  process.exit(2);
}
