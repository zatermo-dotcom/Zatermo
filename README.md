# awesome-copilot installer

A small, dependency-free installer for the customizations published in
[github/awesome-copilot](https://github.com/github/awesome-copilot) — the
community collection of GitHub Copilot **agents, instructions, skills, hooks,
workflows and plugins**.

It clones awesome-copilot once into a local cache, then copies the items you
pick into your project's `.github/` directory, where GitHub Copilot and the
Copilot CLI look for them.

## Requirements

- `bash` and `git` (nothing else)

## Quick start

```bash
# List everything available (or one category)
./install.sh list
./install.sh list skills

# Find something
./install.sh search postgres

# Install specific items (CATEGORY/NAME — extension optional)
./install.sh install agents/postgresql-dba instructions/a11y

# Install a whole category
./install.sh install-all instructions

# See what this project has installed / remove an item
./install.sh installed
./install.sh remove agents/postgresql-dba
```

## Categories

| Category       | What it is                                             | Installs to                        |
| -------------- | ------------------------------------------------------ | ---------------------------------- |
| `agents`       | Specialized Copilot agents (`*.agent.md`)              | `.github/agents/`                  |
| `instructions` | Coding standards applied by file pattern (`*.instructions.md`) | `.github/instructions/`    |
| `skills`       | Self-contained skill folders (`SKILL.md` + assets)     | `.github/skills/<name>/`           |
| `hooks`        | Actions triggered during Copilot agent sessions        | `.github/hooks/<name>/`            |
| `workflows`    | Agentic GitHub Actions workflows (markdown)            | `.github/workflows/`               |
| `plugins`      | Curated bundles of agents and skills                   | `.github/plugins/<name>/`          |

## Commands

| Command                        | Description                                        |
| ------------------------------ | -------------------------------------------------- |
| `list [CATEGORY]`              | List available items                               |
| `search TERM`                  | Search item names and descriptions                 |
| `install CATEGORY/NAME ...`    | Install one or more items                          |
| `install-all CATEGORY`         | Install every item in a category                   |
| `remove CATEGORY/NAME ...`     | Remove installed items                             |
| `installed`                    | Show what this project has installed               |
| `update`                       | Refresh the local cache of awesome-copilot         |

## Options

| Option        | Default             | Description                                   |
| ------------- | ------------------- | --------------------------------------------- |
| `--dest DIR`  | current directory   | Target project root (files land in `DIR/.github/`) |
| `--ref REF`   | `main`              | awesome-copilot git branch/tag to install from |
| `--force`     | off                 | Overwrite existing files without prompting    |
| `-h`, `--help`| —                   | Show usage                                     |

## How it works

- The repository is cloned (shallow) into a cache at
  `${XDG_CACHE_HOME:-~/.cache}/awesome-copilot`. Override with the
  `AWESOME_COPILOT_CACHE` environment variable. `update` refreshes it.
- Installed items are tracked in `.github/.awesome-copilot-manifest.txt` so
  `installed` and `remove` know what came from awesome-copilot.
- Names may be given with or without their extension —
  `agents/postgresql-dba` and `agents/postgresql-dba.agent.md` both work.

## Notes

Items in awesome-copilot are community-contributed. Review anything —
especially `hooks` and `workflows`, which can execute code — before enabling it
in your project.
