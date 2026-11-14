#!/usr/bin/env bash

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -n "${PYTHON:-}" ]] && command -v "$PYTHON" >/dev/null 2>&1; then
    PYTHON_BIN="$PYTHON"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
else
    PYTHON_BIN=""
fi

PASS_COUNT=0
FAIL_COUNT=0
WARNING_COUNT=0

run_hard_step() {
    local step="$1"
    local description="$2"
    shift 2
    printf '\nSTEP %s: %s\n' "$step" "$description"
    if "$@"; then
        printf 'PASS: step %s\n' "$step"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        printf 'FAIL: step %s\n' "$step"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

run_python() {
    [[ -n "$PYTHON_BIN" ]] || {
        printf 'Python interpreter not found (tried python and python3).\n' >&2
        return 127
    }
    "$PYTHON_BIN" "$@"
}

compile_python_files() {
    local file
    local count=0
    local failures=0
    while IFS= read -r -d '' file; do
        count=$((count + 1))
        if ! run_python -m py_compile "$file"; then
            printf '  Compile failed: %s\n' "$file" >&2
            failures=$((failures + 1))
        fi
    done < <(find app ml data -type f -name '*.py' -print0)

    if (( failures > 0 )); then
        printf 'Compiled %s Python files; %s failed.\n' "$count" "$failures"
        return 1
    fi
    printf 'Compiled %s Python files under app/, ml/, and data/.\n' "$count"
}

check_required_files() {
    local file
    local missing=0
    local required_files=(
        "ml/model.pkl"
        "ml/results/metrics.json"
        "ml/results/alert_persistence.json"
        "data/lake_area_south_lhonak.csv"
        "README.md"
    )

    for file in "${required_files[@]}"; do
        if [[ -f "$file" ]]; then
            printf '  PASS: %s exists\n' "$file"
        else
            printf '  FAIL: %s is missing\n' "$file"
            missing=1
        fi
    done

    if [[ -f "docs/report.md" ]]; then
        printf '  PASS: docs/report.md exists\n'
    else
        printf '  WARN: docs/report.md is missing (optional)\n'
        WARNING_COUNT=$((WARNING_COUNT + 1))
    fi

    return "$missing"
}

check_git_ignored_artifacts() {
    local tracked
    local offending
    if ! tracked="$(git ls-files)"; then
        printf 'Could not read tracked paths with git ls-files.\n' >&2
        return 1
    fi
    offending="$(printf '%s\n' "$tracked" | awk '$0 ~ /^venv\// || $0 ~ /^\.venv\// || $0 ~ /\.db$/')"
    if [[ -n "$offending" ]]; then
        printf 'Tracked environment or database paths found:\n%s\n' "$offending"
        return 1
    fi
    printf 'No tracked files under venv/ or .venv/, and no tracked .db files.\n'
}

check_sklearn_version() {
    local pinned
    local installed
    pinned="$(awk -F'==' '$1 == "scikit-learn" { print $2; exit }' requirements.txt)"
    if [[ -z "$pinned" ]]; then
        printf 'WARN: scikit-learn pin not found in requirements.txt.\n'
        WARNING_COUNT=$((WARNING_COUNT + 1))
        return 0
    fi
    if [[ -z "$PYTHON_BIN" ]]; then
        printf 'WARN: cannot read installed scikit-learn version; no Python interpreter found. Pin: %s\n' "$pinned"
        WARNING_COUNT=$((WARNING_COUNT + 1))
        return 0
    fi
    installed="$("$PYTHON_BIN" -c 'from importlib.metadata import PackageNotFoundError, version; print(version("scikit-learn"))' 2>/dev/null)" || installed=""
    if [[ -z "$installed" ]]; then
        printf 'WARN: scikit-learn is not installed; requirements pin: %s\n' "$pinned"
        WARNING_COUNT=$((WARNING_COUNT + 1))
        return 0
    fi
    printf 'scikit-learn installed: %s | pinned in requirements.txt: %s\n' "$installed" "$pinned"
    if [[ "$installed" == "$pinned" ]]; then
        printf 'PASS: step 7 version matches.\n'
    else
        printf 'WARN: installed and pinned scikit-learn versions differ.\n'
        WARNING_COUNT=$((WARNING_COUNT + 1))
    fi
}

run_hard_step 1 "Compile every Python file under app/, ml/, and data/." compile_python_files
run_hard_step 2 "Run the real prediction contract check." run_python -m ml.check_contract
run_hard_step 3 "Run the stub prediction contract check." run_python -m ml.check_contract --stub
run_hard_step 4 "Run the app alert-logic check." run_python -m app.check_alert_logic
run_hard_step 5 "Verify required project files." check_required_files
run_hard_step 6 "Verify venv/, .venv/, and .db files are not tracked." check_git_ignored_artifacts

printf '\nSTEP 7: Compare installed and pinned scikit-learn versions.\n'
check_sklearn_version

printf '\nFinal summary: %s passed, %s failed, %s warning(s).\n' \
    "$PASS_COUNT" "$FAIL_COUNT" "$WARNING_COUNT"
if (( FAIL_COUNT > 0 )); then
    exit 1
fi
exit 0
