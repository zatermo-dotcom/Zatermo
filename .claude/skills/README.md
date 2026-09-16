# Skills catalog

This directory holds several independently sourced skill collections, merged
into one flat tree. Claude Code discovers every subdirectory containing a
`SKILL.md`, so all collections are active at once.

Each collection keeps its own detailed catalog:

| Collection | Catalog | Source |
| --- | --- | --- |
| OmniRoute | [README-omniroute.md](README-omniroute.md) | [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute) |
| Architecture Studio | [README-architecture-studio.md](README-architecture-studio.md) | installed via the skills-architects branch |

Skills outside those two catalogs were installed one collection at a time and
are listed below.

## Engineering workflow

| Skill | Purpose |
| --- | --- |
| `code-simplifier`, `design-patterns`, `performance` | Rust and CLI code quality |
| `rtk-tdd`, `tdd-rust`, `ship` | test-driven workflow and release |
| `pr-review`, `pr-triage`, `issue-triage`, `rtk-triage`, `repo-recap` | repository triage and review |
| `security-guardian` | shell escaping and command-injection review |
| `architecture` | architectural decisions and trade-off records |

## Pre-sales and delivery

| Skill | Purpose |
| --- | --- |
| `new-lead`, `analyze-requirements`, `estimate`, `proposal` | lead intake through client proposal |
| `project-planner` | requirements, design, and task breakdown |
| `project-notetaker`, `workspace-analyzer` | meeting notes and workspace cleanup |

## Media and output

| Skill | Purpose |
| --- | --- |
| `banana` | image generation and editing |
| `remotion-motion-graphics` | React-based motion graphics video |

## Model and token tooling

| Skill | Purpose |
| --- | --- |
| `llm-council` | multi-model deliberation on hard questions |
| `caveman` | compressed output mode |
| `headroom` | Headroom marketplace plugin |
| `ponytail` | minimal-solution coding discipline |

## Adding a collection

Install into `.claude/skills/<skill-name>/SKILL.md`. Before committing, check
that no skill name collides with an existing directory, and that each
manifest's frontmatter `name` matches its directory name.
