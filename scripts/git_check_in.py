#!/usr/bin/env python3
import subprocess
import sys
import atexit

# Track the feature branch for cleanup
pushed_branch = None

def cleanup_and_return_to_develop():
    """Always return to develop and pull before exiting."""
    try:
        current = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False
        ).stdout.strip()
        
        if current != "develop":
            print("\n" + "="*60)
            print("RETURNING TO DEVELOP")
            print("="*60)
            subprocess.run(["git", "checkout", "develop"], check=False)
        
        print("Pulling latest from develop...")
        subprocess.run(["git", "pull", "origin", "develop"], check=False)
        print("✓ You are on develop with latest changes.")
    except:
        pass

# Register cleanup function to run on exit
atexit.register(cleanup_and_return_to_develop)

def run(cmd, check=True, capture_output=False, show_command=True):
    """Run a command and optionally capture output."""
    if show_command:
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
    """Get the current Git branch name."""
    r = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, show_command=False)
    return r.stdout.strip()

def has_merge_conflicts():
    """Check if there are merge conflicts in the working directory."""
    r = run(["git", "status", "--porcelain"], check=False, capture_output=True, show_command=False)
    for line in r.stdout.splitlines():
        if line.startswith(("UU", "AA", "DD")):
            return True
    return False

def list_changed_files():
    """List modified/added files (excluding deletions and ignored files)."""
    r = run(["git", "status", "--porcelain"], capture_output=True, show_command=False)
    files = []
    for line in r.stdout.splitlines():
        status = line[0:2]
        path = line[3:]
        if "D" in status:
            continue
        files.append(path)
    return files

def has_any_changes_from_develop():
    """
    Check if there are any uncommitted or committed changes compared to develop.
    Returns True if there are changes, False if working tree matches develop exactly.
    """
    status_result = run(["git", "status", "--porcelain"], capture_output=True, show_command=False)
    if status_result.stdout.strip():
        return True
    
    current_branch = get_current_branch()
    run(["git", "fetch", "origin", "develop"], capture_output=True, show_command=False, check=False)
    
    diff_result = run(
        ["git", "diff", "--quiet", "origin/develop", "HEAD"],
        check=False,
        capture_output=True,
        show_command=False
    )
    
    return diff_result.returncode != 0

def safe_checkout(branch_name, create_new=False):
    """
    Try to checkout a branch, handle uncommitted changes if checkout fails.
    Returns True if successful, "skip_checkout" if user wants to commit files.
    """
    cmd = ["git", "checkout", "-b", branch_name] if create_new else ["git", "checkout", branch_name]
    
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False, text=True, capture_output=True)
    
    if result.returncode == 0:
        print(result.stdout, end='')
        return True
    
    if "would be overwritten" in result.stderr or "Please commit your changes or stash them" in result.stderr:
        print(result.stderr)
        
        changed_files = list_changed_files()
        
        print("\n" + "="*60)
        print("⚠ You have uncommitted changes blocking the checkout!")
        print("="*60)
        
        if changed_files:
            print("\nFiles with uncommitted changes:")
            for f in changed_files:
                print(f"  - {f}")
        
        print("\nWhat do you want to do?")
        print("1. Commit these files (will continue with check-in)")
        print("2. Stash these changes temporarily")
        print("3. Add to .gitignore and discard (⚠ DESTRUCTIVE)")
        print("4. Abort")
        
        while True:
            choice = input("\nEnter your choice (1-4): ").strip()
            
            if choice == "1":
                print("\n✓ You chose to commit these files.")
                print("The script will continue and include these in your commit.")
                return "skip_checkout"
            
            elif choice == "2":
                print("\n=== Attempting to stash changes ===")
                stash_result = run(
                    ["git", "stash", "push", "-m", "Auto-stash by check-in script"],
                    check=False,
                    capture_output=True
                )
                
                if stash_result.returncode == 0:
                    print("✓ Changes stashed successfully")
                    retry = subprocess.run(cmd, check=False, text=True, capture_output=True)
                    if retry.returncode == 0:
                        print(retry.stdout, end='')
                        print("✓ Checkout successful. Your changes are in stash.")
                        print("  To restore later: git stash pop")
                        return True
                    else:
                        print("ERROR: Checkout still failed:")
                        print(retry.stderr)
                        sys.exit(1)
                else:
                    print("ERROR: Failed to stash:")
                    print(stash_result.stderr)
                    print("Please try another option.")
                    continue
            
            elif choice == "3":
                print("\n⚠⚠⚠ WARNING ⚠⚠⚠")
                print("This will PERMANENTLY DELETE your uncommitted changes!")
                confirm = input("Type 'YES' in all caps to confirm: ").strip()
                
                if confirm == "YES":
                    add_ignore = input("Add these files to .gitignore first? [y/N]: ").strip().lower()
                    
                    if add_ignore == "y" and changed_files:
                        try:
                            with open(".gitignore", "a") as f:
                                f.write("\n# Auto-added by git check-in script\n")
                                for file in changed_files:
                                    f.write(f"{file}\n")
                            print("✓ Files added to .gitignore")
                        except Exception as e:
                            print(f"Warning: Could not update .gitignore: {e}")
                    
                    run(["git", "reset", "--hard", "HEAD"], check=False)
                    run(["git", "clean", "-fd"], check=False)
                    print("✓ Changes discarded")
                    
                    retry = subprocess.run(cmd, check=False, text=True, capture_output=True)
                    if retry.returncode == 0:
                        print(retry.stdout, end='')
                        return True
                    else:
                        print("ERROR: Checkout still failed:")
                        print(retry.stderr)
                        sys.exit(1)
                else:
                    print("Confirmation failed. Trying again...")
                    continue
            
            elif choice == "4":
                print("\nAborting as requested.")
                sys.exit(0)
            
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
    
    else:
        print("ERROR: Checkout failed")
        print(result.stderr)
        sys.exit(1)

def branch_exists(branch_name):
    """Check if a local branch exists."""
    r = run(["git", "branch", "--list", branch_name], capture_output=True, check=False, show_command=False)
    return branch_name in r.stdout.split()

def make_unique_branch_name(base_name):
    """Generate unique branch name by appending _1, _2, etc."""
    if not branch_exists(base_name):
        return base_name
    i = 1
    while True:
        candidate = f"{base_name}_{i}"
        if not branch_exists(candidate):
            return candidate
        i += 1

def is_branch_up_to_date_with_develop(branch_name):
    """Check if branch is up to date with develop."""
    r = run(
        ["git", "merge-base", "--is-ancestor", "develop", branch_name],
        check=False,
        capture_output=True,
        show_command=False
    )
    return r.returncode == 0

def sync_branch_with_develop(branch_name):
    """Sync given branch with develop by merging develop into it."""
    print(f"\n=== Syncing '{branch_name}' with develop ===")
    
    # Make sure we're on the branch
    current = get_current_branch()
    if current != branch_name:
        checkout_result = safe_checkout(branch_name)
        if checkout_result == "skip_checkout":
            print("Skipping checkout for now...")
            return
    
    result = run(["git", "merge", "develop"], check=False, capture_output=True)
    
    if result.returncode != 0:
        if has_merge_conflicts():
            print("\nERROR: Merge conflicts detected while syncing with develop.")
            print("Resolve conflicts manually:")
            print("  1. Fix conflicts in the files")
            print("  2. Run: git add <resolved-files>")
            print("  3. Run: git merge --continue")
            print("  4. Re-run this script")
            sys.exit(1)
        else:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            sys.exit(1)
    
    print(f"✓ Branch '{branch_name}' is now up to date with develop")

def get_conventional_commit_message():
    """Get a commit message following Conventional Commits specification."""
    
    commit_types = {
        "1": ("feat", "A new feature"),
        "2": ("fix", "A bug fix"),
        "3": ("docs", "Documentation only changes"),
        "4": ("style", "Code style changes (formatting, whitespace, etc.)"),
        "5": ("refactor", "Code refactoring (neither fixes a bug nor adds a feature)"),
        "6": ("perf", "Performance improvements"),
        "7": ("test", "Adding or updating tests"),
        "8": ("build", "Changes to build system or dependencies"),
        "9": ("ci", "CI/CD configuration changes"),
        "10": ("chore", "Other changes (maintenance, tooling, etc.)"),
        "11": ("revert", "Reverting a previous commit"),
    }
    
    print("\n=== Conventional Commit Message ===")
    print("Select commit type:")
    for key, (type_name, description) in commit_types.items():
        print(f"  {key}. {type_name:12} - {description}")
    
    while True:
        choice = input("\nEnter your choice (1-11): ").strip()
        if choice in commit_types:
            commit_type = commit_types[choice][0]
            break
        print("Invalid choice. Please enter a number between 1 and 11.")
    
    print(f"\nCommit type: {commit_type}")
    scope = input("Enter scope (optional, e.g., 'api', 'ui', 'auth'): ").strip()
    
    while True:
        description = input("Enter short description (required): ").strip()
        if description:
            break
        print("Description cannot be empty.")
    
    if scope:
        header = f"{commit_type}({scope}): {description}"
    else:
        header = f"{commit_type}: {description}"
    
    print("\nOptional: Add detailed body? (press Enter to skip)")
    body_lines = []
    print("(Enter an empty line when done)")
    while True:
        line = input()
        if not line:
            break
        body_lines.append(line)
    
    footer_lines = []
    add_footer = input("\nAdd footer (e.g., 'Closes #123', 'BREAKING CHANGE: ...')? [y/N]: ").strip().lower()
    if add_footer == "y":
        print("Enter footer lines (press Enter on empty line when done):")
        while True:
            line = input()
            if not line:
                break
            footer_lines.append(line)
    
    commit_msg = header
    if body_lines:
        commit_msg += "\n\n" + "\n".join(body_lines)
    if footer_lines:
        commit_msg += "\n\n" + "\n".join(footer_lines)
    
    print("\n--- Commit Message Preview ---")
    print(commit_msg)
    print("------------------------------")
    
    confirm = input("\nUse this commit message? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Let's try again...")
        return get_conventional_commit_message()
    
    return commit_msg

def main():
    global pushed_branch
    
    # Verify we're in a git repository
    run(["git", "rev-parse", "--is-inside-work-tree"], show_command=False)

    current_branch = get_current_branch()
    print(f"Current branch: {current_branch}")

    # EARLY EXIT: Check if there are any changes at all
    print("\n=== Checking for changes ===")
    if not has_any_changes_from_develop():
        print("\n" + "="*60)
        print("ℹ  NO CHANGES DETECTED")
        print("="*60)
        print("Your working directory has no uncommitted changes,")
        print("and your current branch has no new commits compared to develop.")
        print("\nNothing to commit. Exiting.")
        sys.exit(0)
    
    print("✓ Changes detected. Proceeding with check-in...")

    # STEP 1: Switch to develop and pull latest
    print("\n=== Updating develop branch ===")
    checkout_result = safe_checkout("develop")
    
    if checkout_result == "skip_checkout":
        print("\n✓ Staying on current branch to commit your changes.")
    else:
        run(["git", "pull", "origin", "develop"])
        
        if has_merge_conflicts():
            print("ERROR: Merge conflicts detected while updating develop. Resolve them and rerun.")
            sys.exit(1)

    # STEP 2: Get desired branch name from user
    print("\n=== Creating/selecting feature branch ===")
    
    while True:
        desired_branch = input("Enter branch name (e.g., feature/my-feature): ").strip()
        
        if not desired_branch:
            print("ERROR: Branch name cannot be empty.")
            continue
        
        if desired_branch.lower() in ["develop", "main", "master"]:
            print("ERROR: Cannot use protected branch name.")
            continue
        
        break

    # STEP 3: Handle existing branch or current branch scenario
    final_branch = desired_branch
    current_branch = get_current_branch()
    
    # Case 1: Already on the desired branch OR branch exists
    if current_branch == desired_branch or branch_exists(desired_branch):
        if current_branch == desired_branch:
            print(f"\n✓ You are already on branch '{desired_branch}'")
        else:
            print(f"\n⚠ Branch '{desired_branch}' already exists locally.")
        
        # Ask if they want to update it with develop
        update_branch = input(f"Do you want to update '{desired_branch}' with latest develop? [y/N]: ").strip().lower()
        
        if update_branch == "y":
            # Update the branch with develop
            if current_branch != desired_branch:
                safe_checkout(desired_branch)
            
            if is_branch_up_to_date_with_develop(desired_branch):
                print(f"✓ Branch '{desired_branch}' is already up to date with develop.")
            else:
                sync_branch_with_develop(desired_branch)
            
            final_branch = desired_branch
        else:
            # Create a new branch with "_1" suffix
            final_branch = make_unique_branch_name(desired_branch)
            print(f"\nCreating new branch '{final_branch}' instead.")
            safe_checkout(final_branch, create_new=True)
    else:
        # Branch doesn't exist - create it
        safe_checkout(final_branch, create_new=True)
        print(f"✓ Created and switched to: {final_branch}")

    # STEP 4: List and stage changed files
    print("\n=== Staging files ===")
    files = list_changed_files()
    
    if not files:
        print("No changed files to commit.")
        sys.exit(0)

    print("Files to be committed:")
    for f in files:
        print(f"  - {f}")

    ans = input("\nStage these files? [y/N]: ").strip().lower()
    if ans != "y":
        print("Aborting.")
        sys.exit(0)

    run(["git", "add"] + files)

    # STEP 5: Create commit
    commit_msg = get_conventional_commit_message()
    run(["git", "commit", "-m", commit_msg])

    # STEP 6: Push
    print("\n=== Pushing to remote ===")
    current_branch = get_current_branch()
    
    if current_branch.lower() in ["develop", "main", "master"]:
        print(f"FATAL ERROR: Cannot push to protected branch '{current_branch}'!")
        sys.exit(1)

    print(f"Ready to push to: origin/{current_branch}")
    ans = input("Proceed with push? [y/N]: ").strip().lower()
    
    if ans != "y":
        print("Commit created locally but not pushed.")
        print(f"To push later: git push -u origin {current_branch}")
        sys.exit(0)
    
    run(["git", "push", "-u", "origin", current_branch])
    pushed_branch = current_branch
    
    print(f"\n✓ Successfully pushed to origin/{current_branch}")
    print(f"\n{'='*60}")
    print("NEXT STEPS")
    print(f"{'='*60}")
    print(f"1. Create a Pull/Merge Request from '{current_branch}' to 'develop'")
    print("2. Wait for PR approval and merge")
    print("\n✓ Check-in complete!")
    
    # The atexit handler will automatically:
    # - Switch to develop
    # - Pull latest from develop

if __name__ == "__main__":
    main()
