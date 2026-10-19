#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$SCRIPT_DIR"

usage() {
    cat <<'EOF'
Usage: ./create_github_repo.sh [REPO_NAME] [--public|--private]

Create a GitHub repository for this directory, make an initial commit if
needed, add "origin", and push the current branch.

Arguments:
  REPO_NAME             Repository name or owner/name.
                        Defaults to the name of this directory.

Options:
  --public              Create a public repository.
  --private             Create a private repository (default).
  -h, --help            Show this help.

Environment:
  VISIBILITY            "public" or "private" (default: private).
  GIT_BRANCH            Branch name for a new local repository (default: main).
  REPO_DESCRIPTION      GitHub repository description.

Prerequisites:
  git, the GitHub CLI (gh), and an authenticated session from `gh auth login`.
  Git user.name and user.email must also be configured.
EOF
}

REPO_NAME=""
VISIBILITY="${VISIBILITY:-private}"
GIT_BRANCH="${GIT_BRANCH:-main}"
REPO_DESCRIPTION="${REPO_DESCRIPTION:-A practical, dependency-free SAS to R converter with examples}"

while (($# > 0)); do
    case "$1" in
        --public)
            VISIBILITY="public"
            ;;
        --private)
            VISIBILITY="private"
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --*)
            printf 'Unknown option: %s\n\n' "$1" >&2
            usage >&2
            exit 2
            ;;
        *)
            if [[ -n "$REPO_NAME" ]]; then
                printf 'Only one repository name may be supplied.\n' >&2
                exit 2
            fi
            REPO_NAME="$1"
            ;;
    esac
    shift
done

if [[ "$VISIBILITY" != "public" && "$VISIBILITY" != "private" ]]; then
    printf 'VISIBILITY must be "public" or "private".\n' >&2
    exit 2
fi

REPO_NAME="${REPO_NAME:-$(basename "$SCRIPT_DIR")}"

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

command -v git >/dev/null 2>&1 || fail "Git is not installed."
command -v gh >/dev/null 2>&1 || fail \
    "GitHub CLI is not installed. See https://cli.github.com/."

gh auth status >/dev/null 2>&1 || fail \
    "GitHub CLI is not authenticated. Run: gh auth login"

git config --get user.name >/dev/null 2>&1 || fail \
    "Git user.name is not configured. Run: git config --global user.name \"Your Name\""
git config --get user.email >/dev/null 2>&1 || fail \
    "Git user.email is not configured. Run: git config --global user.email \"you@example.com\""

[[ -f README.md ]] || fail "README.md is missing from $SCRIPT_DIR."

if git rev-parse --show-toplevel >/dev/null 2>&1; then
    GIT_ROOT="$(git rev-parse --show-toplevel)"
    if [[ "$GIT_ROOT" != "$SCRIPT_DIR" ]]; then
        fail "This directory is inside the Git repository at $GIT_ROOT. Create the repository from a standalone directory."
    fi
fi

if [[ ! -e .git ]]; then
    printf 'Initializing Git repository on branch %s...\n' "$GIT_BRANCH"
    git init -b "$GIT_BRANCH" >/dev/null
    git add -A
    git commit -m "Initial commit: SAS to R converter"
else
    if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
        printf 'Creating the initial commit...\n'
        git add -A
        git commit -m "Initial commit: SAS to R converter"
    elif [[ -n "$(git status --porcelain)" ]]; then
        fail "The local repository has uncommitted changes. Commit or stash them first."
    fi
fi

if git remote get-url origin >/dev/null 2>&1; then
    fail "A Git remote named 'origin' already exists."
fi

if gh repo view "$REPO_NAME" >/dev/null 2>&1; then
    fail "GitHub repository '$REPO_NAME' already exists."
fi

printf 'Creating GitHub repository %s (%s)...\n' "$REPO_NAME" "$VISIBILITY"
gh repo create "$REPO_NAME" \
    "--$VISIBILITY" \
    --source=. \
    --remote=origin \
    --push \
    --description "$REPO_DESCRIPTION"

REPO_URL="$(gh repo view "$REPO_NAME" --json url --jq .url)"
printf 'Created repository: %s\n' "$REPO_URL"
