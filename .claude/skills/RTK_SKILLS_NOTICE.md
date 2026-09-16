# RTK Assets — Source & License

The Claude Code assets listed below were installed from the RTK project:

- Source: https://github.com/rtk-ai/rtk (`.claude/`)
- License: Apache License 2.0 — https://github.com/rtk-ai/rtk/blob/main/LICENSE

**Skills** (`.claude/skills/`): `code-simplifier`, `design-patterns`,
`issue-triage`, `performance`, `pr-review`, `pr-triage`, `repo-recap`,
`rtk-tdd`, `rtk-triage`, `security-guardian`, `ship`, `tdd-rust`.

**Agents** (`.claude/agents/`): `code-reviewer`, `debugger`,
`rtk-testing-specialist`, `rust-rtk`, `system-architect`, `technical-writer`.

**Rules** (`.claude/rules/`): `cli-testing`, `rust-patterns`, `search-strategy`.

**Commands** (`.claude/commands/`): worktree management, `codereview`,
`audit-codebase`, `diagnose`, `test-routing`, and RTK workflow commands.

**Hooks** (`.claude/hooks/`): `rtk-suggest.sh`, `rtk-rewrite.sh`,
`bash/pre-commit-format.sh`. These are inert — no `settings.json` entry
registers them, so nothing runs until they are wired up explicitly.

Files are unmodified copies of the upstream originals.
