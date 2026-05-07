# auto-yolo-dataset-skill

One-command installer for the `auto-yolo-dataset` Codex/Claude Code skill.

## Install

After this package is published to npm:

```bash
npx --yes auto-yolo-dataset-skill
```

Until it is published, install from a GitHub repo that contains this package at the repository root:

```bash
npx --yes github:WdBlink/auto-yolo-dataset-skill
```

The default installer copies the skill into both:

- `~/.codex/skills/auto-yolo-dataset`
- `~/.claude/skills/auto-yolo-dataset`

## Options

```bash
npx auto-yolo-dataset-skill --codex-only
npx auto-yolo-dataset-skill --claude-only
npx auto-yolo-dataset-skill --target ~/.codex/skills
npx auto-yolo-dataset-skill --dry-run
```

`--target` expects a skills root directory. For example, pass `~/.codex/skills`, not `~/.codex/skills/auto-yolo-dataset`.

Use the skill in Codex with:

```text
$auto-yolo-dataset
```

Use the skill in Claude Code with:

```text
/auto-yolo-dataset
```
