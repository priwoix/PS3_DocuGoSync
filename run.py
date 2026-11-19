
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CPP_DIR = ROOT / "CPP_engine"
PY_DIR = ROOT / "Python_engine"


def run_command(command, cwd=None, capture=True):
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=capture
    )
    if result.returncode != 0:
        error = result.stderr if capture else "Command failed"
        raise RuntimeError(f"Command failed: {' '.join(map(str, command))}\n{error}")
    return result.stdout if capture else ""


def git_ref(repo, ref):
    candidates = [ref, f"origin/{ref}"]
    for candidate in candidates:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"{candidate}^{{commit}}"],
            cwd=repo, text=True, capture_output=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    raise RuntimeError(f"Could not find Git commit or branch: {ref}")


def git_file(repo, commit, path):
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=repo, capture_output=True
    )
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="replace")


def get_language(path):
    ext = Path(path).suffix.lower()
    languages = {
        ".cpp": "C++", ".cc": "C++", ".cxx": "C++",
        ".h": "C++", ".hpp": "C++",
        ".py": "Python", ".js": "JavaScript",
        ".ts": "TypeScript", ".java": "Java",
        ".c": "C", ".go": "Go", ".rs": "Rust",
        ".html": "HTML", ".css": "CSS"
    }
    return languages.get(ext, "Other")



def find_readme(repo, commit):
    files = run_command(
        ["git", "ls-tree", "-r", "--name-only", commit],
        cwd=repo
    ).splitlines()

    candidates = [
        f for f in files
        if Path(f).name.lower().startswith("readme.")
        or Path(f).name.lower() == "readme"
    ]

    if not candidates:
        raise RuntimeError(
            "No README found in this commit. "
            "Choose a repository containing a README file."
        )

    candidates.sort(key=lambda p: ("/" in p, len(p)))
    return candidates[0]



def ensure_cpp_executable():
    exe_name = "extractor.exe" if os.name == "nt" else "extractor"
    exe = CPP_DIR / exe_name

    if exe.exists():
        return exe

    print("C++ executable missing. Compiling engine...")
    command = [
        "g++", "-std=c++17", "-I", "include",
        "src/main.cpp", "src/constant_extractor.cpp",
        "-o", exe_name
    ]
    run_command(command, cwd=CPP_DIR)
    return exe


def analyse_cpp_files(repo, base, head, changed_cpp):
    if not changed_cpp:
        return []

    exe = ensure_cpp_executable()
    old_file = CPP_DIR / "test_data" / "old.cpp"
    new_file = CPP_DIR / "test_data" / "new.cpp"
    output_file = CPP_DIR / "output" / "changes.json"

    # Preserve the original test files.
    old_backup = old_file.read_bytes() if old_file.exists() else None
    new_backup = new_file.read_bytes() if new_file.exists() else None

    all_changes = []

    try:
        for item in changed_cpp:
            old_path = item.get("old_path", item["path"])
            new_path = item.get("new_path", item["path"])

            old_content = (
                git_file(repo, base, old_path)
                if item["status"] != "added" else ""
            )
            new_content = (
                git_file(repo, head, new_path)
                if item["status"] != "deleted" else ""
            )

            old_file.write_text(old_content, encoding="utf-8")
            new_file.write_text(new_content, encoding="utf-8")

            run_command([str(exe)], cwd=CPP_DIR)

            if output_file.exists():
                result = json.loads(output_file.read_text(encoding="utf-8"))
                for change in result.get("changes", []):
                    change["file"] = item["path"]
                    all_changes.append(change)

    finally:
        if old_backup is not None:
            old_file.write_bytes(old_backup)
        if new_backup is not None:
            new_file.write_bytes(new_backup)

    counts = {"added": 0, "removed": 0, "modified": 0}
    for change in all_changes:
        kind = change.get("change_type", "").lower()
        if kind in counts:
            counts[kind] += 1

    return {
        "language": "cpp",
        "status": "success",
        "total_changes": len(all_changes),
        "summary": counts,
        "changes": all_changes
    }


def main():
    parser = argparse.ArgumentParser(
        description="Compare GitHub code changes against README documentation."
    )
    parser.add_argument("repo_url", help="GitHub repository URL")
    parser.add_argument("base", help="Older commit or branch")
    parser.add_argument("head", help="Newer commit or branch")
    args = parser.parse_args()

    print("\n[1/6] Cloning repository...")
    with tempfile.TemporaryDirectory() as temp:
        repo = Path(temp) / "repo"
        run_command(["git", "clone", args.repo_url, str(repo)])

        run_command(["git", "fetch", "--all", "--tags"], cwd=repo)

        base = git_ref(repo, args.base)
        head = git_ref(repo, args.head)

        print("[2/6] Detecting changed files...")
        diff = run_command(
            ["git", "diff", "--name-status", "--find-renames", base, head],
            cwd=repo
        )

        changed_files = []
        for line in diff.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue

            git_status = parts[0]
            if git_status.startswith("R") or git_status.startswith("C"):
                old_path, new_path = parts[1], parts[2]
                path = new_path
            else:
                old_path = new_path = parts[1]
                path = parts[1]

            status = (
                "added" if git_status == "A" else
                "deleted" if git_status == "D" else
                "renamed" if git_status.startswith("R") else
                "modified"
            )

            changed_files.append({
                "path": path,
                "old_path": old_path,
                "new_path": new_path,
                "status": status,
                "language": get_language(path)
            })

        cpp_files = [
            f for f in changed_files
            if f["language"] == "C++"
        ]

        print(f"    Found {len(changed_files)} changed files.")
        print(f"    C++ files to analyse: {len(cpp_files)}")

        print("[3/6] Running C++ analysis...")
        changes_json = analyse_cpp_files(repo, base, head, cpp_files)

        if not changes_json:
            changes_json = {
                "language": "cpp",
                "status": "success",
                "total_changes": 0,
                "summary": {"added": 0, "removed": 0, "modified": 0},
                "changes": []
            }

        changes_path = CPP_DIR / "output" / "changes.json"
        changes_path.parent.mkdir(parents=True, exist_ok=True)
        changes_path.write_text(
            json.dumps(changes_json, indent=2),
            encoding="utf-8"
        )

        print("[4/6] Extracting README documentation...")
        readme_path = find_readme(repo, head)
        readme_content = git_file(repo, head, readme_path)

        input_dir = PY_DIR / "input"
        output_dir = PY_DIR / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        current_readme = input_dir / "README_current.md"
        current_readme.write_text(readme_content, encoding="utf-8")

        run_command(
            [sys.executable, "extractor.py", str(current_readme)],
            cwd=PY_DIR
        )

        print("[5/6] Comparing code changes with documentation...")
        run_command(
            [
                sys.executable, "comparer.py",
                str(changes_path),
                str(output_dir / "docs.json")
            ],
            cwd=PY_DIR
        )

        verdict_path = output_dir / "verdict.json"
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))

        print("[6/6] Creating unified report...")
        unsupported = [
            f for f in changed_files
            if f["language"] != "C++"
        ]

        report = {
            "repository": args.repo_url,
            "base_commit": base,
            "head_commit": head,
            "readme_used": readme_path,
            "changed_files": changed_files,
            "unsupported_files": unsupported,
            "summary": {
                "changed_files": len(changed_files),
                "cpp_files_analyzed": len(cpp_files),
                "code_changes": changes_json["total_changes"],
                "documentation_findings": len(verdict.get("findings", []))
            },
            "code_changes": changes_json.get("changes", []),
            "findings": verdict.get("findings", [])
        }

        report_json = json.dumps(report, indent=2)

        (ROOT / "report.json").write_text(report_json, encoding="utf-8")
        (output_dir / "report.json").write_text(report_json, encoding="utf-8")

        print("\nSUCCESS! Report generated:")
        print(ROOT / "report.json")
        print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {error}")
        sys.exit(1)
