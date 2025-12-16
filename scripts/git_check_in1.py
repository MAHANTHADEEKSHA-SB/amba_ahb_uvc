#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import re
import subprocess
import sys

def run(cmd, check=True, capture=False):
    kwargs = {"check": False, "universal_newlines": True}
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    p = subprocess.run(cmd, **kwargs)
    if check and p.returncode != 0:
        if capture:
            if p.stdout:
                sys.stdout.write(p.stdout)
            if p.stderr:
                sys.stderr.write(p.stderr)
        sys.exit(p.returncode)
    return p

def git(*args, check=True, capture=False):
    return run(["git"] + list(args), check=check, capture=capture)

def ensure_clean_worktree():
    r = git("status", "--porcelain", capture=True, check=True)
    if (r.stdout or "").strip():
        sys.exit("ERROR: Working tree not clean. Commit/stash changes before tagging a release.")

def current_branch():
    r = git("rev-parse", "--abbrev-ref", "HEAD", capture=True, check=True)
    return (r.stdout or "").strip()

def tag_exists(tag):
    r = git("rev-parse", "-q", "--verify", "refs/tags/" + tag, check=False, capture=False)
    return r.returncode == 0

def validate_semver(version):
    # SemVer core: X.Y.Z where X,Y,Z are non-negative integers (no leading +/spaces).
    # Keeping it strict per your request; extend if you need -rc.1 / +meta.
    return re.match(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$", version) is not None

def main():
    ap = argparse.ArgumentParser(description="Create/push an annotated SemVer tag from develop only (Python 3.6).")
    ap.add_argument("--version", required=True, help="SemVer version like 1.2.3")
    ap.add_argument("--remote", default="origin", help="Remote name (default: origin)")
    ap.add_argument("--develop", default="develop", help="Develop branch name (default: develop)")
    ap.add_argument("--tag-prefix", default="v", help="Tag prefix (default: v) -> v1.2.3")
    ap.add_argument("--message", default=None, help="Optional tag message (default: 'Release <tag>')")
    ap.add_argument("--force", action="store_true", help="If tag exists, delete & recreate it (dangerous).")
    args = ap.parse_args()

    if not validate_semver(args.version):
        sys.exit("ERROR: version must be strict SemVer 'MAJOR.MINOR.PATCH' (example: 1.2.3).")

    tag = "{}{}".format(args.tag_prefix, args.version)
    msg = args.message if args.message else "Release {}".format(tag)

    # Ensure we're in a repo
    git("rev-parse", "--is-inside-work-tree", check=True, capture=True)

    # Must tag from develop only
    br = current_branch()
    if br != args.develop:
        sys.exit("ERROR: Must be on '{}' to create a release tag (current: {}).".format(args.develop, br))

    ensure_clean_worktree()

    # Update develop to latest remote
    git("fetch", args.remote, args.develop, check=True, capture=False)
    git("pull", args.remote, args.develop, check=True, capture=False)

    # Create annotated tag (optionally force)
    if tag_exists(tag):
        if not args.force:
            sys.exit("ERROR: Tag already exists: {} (use --force to recreate/move it).".format(tag))
        git("tag", "-d", tag, check=False, capture=True)
        # Also delete remote tag before re-pushing
        git("push", args.remote, ":refs/tags/{}".format(tag), check=False, capture=True)

    git("tag", "-a", tag, "-m", msg, check=True, capture=False)
    git("push", args.remote, tag, check=True, capture=False)

    print("OK: Created and pushed annotated tag '{}' from '{}'.".format(tag, args.develop))

if __name__ == "__main__":
    main()
