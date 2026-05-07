---
name: migration
description: Portability guidance for Codex, Claude Code, Gamma 4, and other agent hosts.
---

# Migration

Keep the workflow stable across hosts:

1. Host agent reads images or calls a vision backend.
2. Host agent writes the annotation contract JSON.
3. Host agent runs `scripts/build_yolo_dataset.py`.
4. Host agent reports generated assets and annotation limitations.

## Gamma 4 Adapter Boundary

A future Gamma 4 integration only needs to implement this function:

```text
images + class hints + output manifest path -> annotation-contract JSON
```

Do not let Gamma 4-specific request fields leak into the builder. Store backend details in optional `source` or `notes` fields if needed.

## Cross-Host Constraints

- Use relative paths in manifests whenever possible.
- Do not require a slash command such as `/opc` or a Codex-only tool.
- Do not call network APIs from the dataset builder.
- Do not write outside the requested output directory except for reading source images.
- Keep scripts executable with the system Python standard library.
