#!/usr/bin/env bash
# tools/delegate/worktree.sh
#
# Worktree + result lifecycle for delegate slots. Thin wrapper around
# `git worktree` with conventions for delegate branches.
#
# Usage:
#   worktree.sh create  SLOT        # create or reuse worktree + branch
#   worktree.sh list                # list all delegate worktrees
#   worktree.sh show    SLOT        # show commits + diffstat on the slot branch
#   worktree.sh path    SLOT        # print absolute path to the slot's worktree
#   worktree.sh merge   SLOT        # fast-forward or merge slot branch into HEAD
#   worktree.sh discard SLOT        # remove worktree + delete branch (destructive)

set -euo pipefail
DELEGATE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$DELEGATE_DIR/lib.sh"

cmd="${1:-}"
slot="${2:-}"

require_slot() {
    [[ -n "$slot" ]] || die "slot required (usage: worktree.sh $cmd SLOT)"
}

case "$cmd" in
    create)
        require_slot
        ensure_worktree "$slot"
        echo "$(worktree_path "$slot")"
        ;;

    list)
        ( cd "$REPO_ROOT" && git worktree list ) | grep -E '(^|\s)delegate-|\[delegate/' || {
            info "no delegate worktrees"
            exit 0
        }
        ;;

    path)
        require_slot
        echo "$(worktree_path "$slot")"
        ;;

    show)
        require_slot
        wt_path="$(worktree_path "$slot")"
        [[ -d "$wt_path" ]] || die "no worktree for slot '$slot' at $wt_path"
        branch="$(worktree_branch "$slot")"
        info "branch: $branch"
        info "path:   $wt_path"
        echo
        echo "── commits since master ─────────────────────────────"
        ( cd "$REPO_ROOT" && git log --oneline "master..$branch" 2>/dev/null ) || echo "(none)"
        echo
        echo "── diffstat vs master ───────────────────────────────"
        ( cd "$REPO_ROOT" && git diff --stat "master..$branch" 2>/dev/null ) || echo "(none)"
        ;;

    merge)
        require_slot
        branch="$(worktree_branch "$slot")"
        ( cd "$REPO_ROOT"
          current="$(git rev-parse --abbrev-ref HEAD)"
          info "merging $branch → $current"
          git merge --no-ff "$branch"
        )
        ;;

    discard)
        require_slot
        wt_path="$(worktree_path "$slot")"
        branch="$(worktree_branch "$slot")"
        if [[ -d "$wt_path" ]]; then
            info "removing worktree: $wt_path"
            ( cd "$REPO_ROOT" && git worktree remove --force "$wt_path" )
        else
            info "no worktree to remove at $wt_path"
        fi
        if ( cd "$REPO_ROOT" && git show-ref --verify --quiet "refs/heads/$branch" ); then
            info "deleting branch: $branch"
            ( cd "$REPO_ROOT" && git branch -D "$branch" )
        fi
        ;;

    -h|--help|"")
        sed -n '1,14p' "$0"
        ;;

    *)
        die "unknown subcommand: $cmd (try: create|list|show|path|merge|discard)"
        ;;
esac
