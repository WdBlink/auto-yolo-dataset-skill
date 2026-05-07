#!/usr/bin/env node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";

const root = process.cwd();
const packJson = execFileSync("npm", ["pack", "--dry-run", "--json"], {
  cwd: root,
  encoding: "utf8"
});
const [pack] = JSON.parse(packJson);
const files = pack.files.map((item) => item.path).sort();
const forbidden = files.filter((file) =>
  file.startsWith("images/") ||
  file.startsWith("dataset/") ||
  file.startsWith("reports/") ||
  file.startsWith("tmp/") ||
  file.startsWith("tests/fixtures/") ||
  file.includes("__pycache__") ||
  file.endsWith(".pyc")
);
if (forbidden.length > 0) {
  throw new Error(`Forbidden files in npm package: ${forbidden.join(", ")}`);
}
for (const required of [
  "bin/install.mjs",
  "auto-yolo-dataset/SKILL.md",
  "auto-yolo-dataset/scripts/build_yolo_dataset.py"
]) {
  if (!files.includes(required)) throw new Error(`Missing package file: ${required}`);
}

const home = fs.mkdtempSync(path.join(os.tmpdir(), "auto-yolo-skill-home-"));
try {
  execFileSync("node", ["bin/install.mjs", "--home", home], { cwd: root, stdio: "pipe" });
  for (const skillRoot of [".codex/skills", ".claude/skills"]) {
    const skillDir = path.join(home, skillRoot, "auto-yolo-dataset");
    if (!fs.existsSync(path.join(skillDir, "SKILL.md"))) {
      throw new Error(`Missing installed SKILL.md under ${skillDir}`);
    }
    execFileSync("python", [path.join(skillDir, "scripts", "build_yolo_dataset.py"), "--help"], {
      stdio: "pipe"
    });
  }
} finally {
  fs.rmSync(home, { recursive: true, force: true });
}

console.log("packaging smoke passed");
