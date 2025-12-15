#!/usr/bin/env python3
import subprocess
import sys

def run(cmd, check=True, capture_output=False):
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=capture_output,
    )
    if check and result.returncode != 0:
        if capture_output:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result

def get_current_branch():
    r = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True)
    return r.stdout.strip()

def has_merge_conflicts():
    r = run(["git", "status", "--porcelain"], check=False, capture_output=True)
    for line in r.stdout.splitlines():
        if line.startswith(("UU", "AA", "DD")):
            return True
    return False

def list_changed_files_not_ignored():
    r = run(["git", "status", "--porcelain"], capture_output=True)
    files = []
    for line in r.stdout.splitlines():
        status = line[0:2]
        path = line[3:]
        if "D" in status:
            continue
        files.append(path)
    return files

def branch_exists(branch_name):
    # check local branches only; add --all if you want remote too
    r = run(["git", "branch", "--list", branch_name], capture_output=True)
    return branch_name in r.stdout.split()

def make_unique_branch_name(base_name):
    """Generate base_name, base_name_1, base_name_2, ... until free."""
    if not branch_exists(base_name):
        return base_name
    i = 1
    while True:
        candidate = f"{base_name}_{i}"
        if not branch_exists(candidate):
            return candidate
        i += 1

def fast_forward_with_develop(target_branch):
    """
    Ensure target_branch has latest develop:
    - switch to target_branch
    - git fetch origin
    - git switch develop && git pull origin develop
    - git switch target_branch && git merge develop
    """
    # make sure we have latest remote info
    run(["git", "fetch", "origin"])
    # update develop
    run(["git", "switch", "develop"])
    run(["git", "pull", "origin", "develop"])

    if has_merge_conflicts():
        print("Conflicts while updating develop. Resolve them first.")
        sys.exit(1)

    # merge develop into target branch
    run(["git", "switch", target_branch])
    run(["git", "merge", "develop"], check=False)  # may be 'Already up to date.'

    if has_merge_conflicts():
        print(f"Conflicts while merging develop into {target_branch}. Resolve them and rerun.")
        sys.exit(1)

def main():
    run(["git", "rev-parse", "--is-inside-work-tree"])

    current_branch = get_current_branch()
    print(f"Current branch: {current_branch}")

    if current_branch != "develop":
        ans = input("You are not on 'develop'. Pull from 'develop' before this check‑in? [y/N]: ").strip().lower()
        if ans == "y":
            run(["git", "switch", "develop"])
            run(["git", "pull", "origin", "develop"])
            if has_merge_conflicts():
                print("Merge conflicts detected after pulling 'develop'. Resolve them manually and rerun.")
                sys.exit(1)
        else:
            print("Skipping pull from develop as requested.")

    # decide branch to work on
    current_branch = get_current_branch()
    if current_branch == "develop":
        base_branch_name = input("Enter branch name for this check‑in: ").strip()
        if not base_branch_name:
            print("Branch name cannot be empty.")
            sys.exit(1)

        if branch_exists(base_branch_name):
            print(f"Branch '{base_branch_name}' already exists.")
            use_existing = input("Do you want to switch to this existing branch? [y/N]: ").strip().lower()
            if use_existing == "y":
                # switch and ensure it is up to date with develop
                run(["git", "switch", base_branch_name])
                fast_forward_with_develop(base_branch_name)
            else:
                # create a unique branch name with suffix
                new_name = make_unique_branch_name(base_branch_name)
                print(f"Creating new branch '{new_name}' instead.")
                run(["git", "switch", "-c", new_name])
                current_branch = new_name
        else:
            # create branch normally
            run(["git", "switch", "-c", base_branch_name])
            current_branch = base_branch_name
    else:
        print(f"Working on existing branch '{current_branch}' (not develop).")

    files = list_changed_files_not_ignored()
    if not files:
        print("No changed files to commit.")
        sys.exit(0)

    print("Files to be added:")
    for f in files:
        print("  ", f)

    ans = input("Stage these files? [y/N]: ").strip().lower()
    if ans != "y":
        print("Aborting as requested.")
        sys.exit(0)

    run(["git", "add"] + files)

    feat_id = input("Enter feature/issue ID for commit message (inside feat(...)): ").strip()
    msg = input("Enter commit message: ").strip()
    if not msg:
        print("Commit message cannot be empty.")
        sys.exit(1)

    commit_msg = f"feat({feat_id}): {msg}" if feat_id else f"feat: {msg}"
    run(["git", "commit", "-m", commit_msg])

    ans = input(f"Push to origin {current_branch}? [y/N]: ").strip().lower()
    if ans == "y":
        run(["git", "push", "origin", current_branch])
    else:
        print("Commit created but not pushed.")

if __name__ == "__main__":
    main()

