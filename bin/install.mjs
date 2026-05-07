#!/usr/bin/env node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const packageRoot = path.resolve(path.dirname(__filename), "..");
const sourceSkill = path.join(packageRoot, "auto-yolo-dataset");
const skillName = "auto-yolo-dataset";

function usage() {
  return `Usage:
  npx auto-yolo-dataset-skill [options]

Options:
  --codex-only          Install only to ~/.codex/skills
  --claude-only         Install only to ~/.claude/skills
  --home <path>         Use a custom home directory for installation
  --target <path>       Install to a specific skills directory
  --dry-run             Print actions without writing files
  -h, --help            Show this help

Default:
  Install the skill to both Codex and Claude Code skill roots.
`;
}

function parseArgs(argv) {
  const options = {
    codex: true,
    claude: true,
    home: process.env.HOME || os.homedir(),
    targets: [],
    dryRun: false
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--codex-only") {
      options.codex = true;
      options.claude = false;
    } else if (arg === "--claude-only") {
      options.codex = false;
      options.claude = true;
    } else if (arg === "--home") {
      i += 1;
      if (!argv[i]) throw new Error("--home requires a path");
      options.home = path.resolve(argv[i]);
    } else if (arg === "--target") {
      i += 1;
      if (!argv[i]) throw new Error("--target requires a path");
      options.targets.push(path.resolve(argv[i]));
    } else if (arg === "--dry-run") {
      options.dryRun = true;
    } else if (arg === "-h" || arg === "--help") {
      console.log(usage());
      process.exit(0);
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }
  return options;
}

function ensureInsideHome(target, home) {
  const resolved = path.resolve(target);
  const resolvedHome = path.resolve(home);
  if (!resolved.startsWith(`${resolvedHome}${path.sep}`)) {
    throw new Error(`Refusing to install outside home directory without --target: ${resolved}`);
  }
}

async function copyDir(src, dest) {
  await fs.promises.mkdir(path.dirname(dest), { recursive: true });
  await fs.promises.cp(src, dest, {
    recursive: true,
    dereference: true,
    filter: (entry) => !entry.includes("__pycache__") && !entry.endsWith(".pyc")
  });
}

async function installAtomically(src, dest) {
  const parent = path.dirname(dest);
  await fs.promises.mkdir(parent, { recursive: true });
  const nonce = `${process.pid}-${Date.now()}`;
  const temp = path.join(parent, `.${path.basename(dest)}.tmp-${nonce}`);
  const backup = path.join(parent, `.${path.basename(dest)}.backup-${nonce}`);
  await fs.promises.rm(temp, { recursive: true, force: true });
  await fs.promises.rm(backup, { recursive: true, force: true });
  await copyDir(src, temp);
  let hadExisting = false;
  try {
    await fs.promises.lstat(dest);
    hadExisting = true;
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }

  try {
    if (hadExisting) await fs.promises.rename(dest, backup);
    await fs.promises.rename(temp, dest);
    await fs.promises.rm(backup, { recursive: true, force: true });
  } catch (error) {
    await fs.promises.rm(temp, { recursive: true, force: true });
    if (hadExisting) {
      try {
        await fs.promises.lstat(dest);
      } catch (destError) {
        if (destError.code === "ENOENT") {
          await fs.promises.rename(backup, dest);
        }
      }
    }
    throw error;
  }
}

function destinationRoots(options) {
  if (options.targets.length > 0) return options.targets;
  const roots = [];
  if (options.codex) roots.push(path.join(options.home, ".codex", "skills"));
  if (options.claude) roots.push(path.join(options.home, ".claude", "skills"));
  return roots;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const roots = destinationRoots(options);
  if (!fs.existsSync(path.join(sourceSkill, "SKILL.md"))) {
    throw new Error(`Bundled skill not found: ${sourceSkill}`);
  }
  if (roots.length === 0) {
    throw new Error("No install targets selected");
  }

  const installed = [];
  for (const root of roots) {
    if (options.targets.length === 0) ensureInsideHome(root, options.home);
    const dest = path.join(root, skillName);
    if (options.dryRun) {
      console.log(`[dry-run] install ${sourceSkill} -> ${dest}`);
    } else {
      await installAtomically(sourceSkill, dest);
      installed.push(dest);
      console.log(`Installed ${skillName} -> ${dest}`);
    }
  }

  if (!options.dryRun) {
    console.log("");
    console.log("Done. Restart or refresh your agent session if the skill list was already loaded.");
    console.log("Trigger with: $auto-yolo-dataset");
  }
}

main().catch((error) => {
  console.error(`ERROR: ${error.message}`);
  process.exit(1);
});
