# mwg-guide-reach

An offline reachability auditor for [Modern Web Guidance](https://github.com/GoogleChrome/modern-web-guidance-src) guide corpora: it reports every `guide.md` that exists on disk but can never be reached by the upstream inventory, plus the duplicate and stub artifacts those invisible directories hide.

Why now: the guide corpus passed 250 guides and is consumed by coding agents through a generated inventory. An artifact that is not in that inventory is not just dead weight — it is silently unaudited, so a duplicate id or a TODO-only demo can ship without any test noticing.

Upstream: https://github.com/GoogleChrome/modern-web-guidance-src

## The gap this fills

`scanAllGuides()` in `src/core/guide-validation.ts` walks exactly two levels: `guides/<category>/<guide>/guide.md`. It never recurses:

- source: https://github.com/GoogleChrome/modern-web-guidance-src/blob/main/src/core/guide-validation.ts#L826-L847
- the loop reads `guides/` categories, then one level of guide directories, and stops.

The consequence is tracked upstream in an open bug report filed against `main` on 2026-11-12:

- https://github.com/GoogleChrome/modern-web-guidance-src/issues/3536
- “`scanAllGuides()` only inventories `guides/<category>/<guide>/` directories. A nested directory containing `guide.md` is not discovered or validated.”
- the report names a real tracked example: https://github.com/GoogleChrome/modern-web-guidance-src/tree/main/guides/performance/deliver-optimized-decorative-images/serve-alternative-image-formats

This tool measures that blind spot independently, without importing upstream code and without trusting the upstream test suite. It does not patch upstream and it does not guess at intent: every finding is a path plus the rule that fired.

## What it does

Given a repository root, it walks `guides/`, parses the top-level `name:` from each `guide.md` frontmatter, and classifies every artifact against the inventory contract:

| Rule | Severity | Meaning |
| --- | --- | --- |
| `UNREACHABLE_GUIDE` | error | `guide.md` is deeper than `guides/<category>/<guide>/`; the inventory never sees it |
| `DUPLICATE_GUIDE_ID` | error | the same frontmatter `name` is declared by more than one file |
| `STUB_DEMO` | error | `demo.html` has no content outside HTML comments and there is no `targets/` or `tasks/` directory |
| `STUB_EXPECTATIONS` | warning | `expectations.md` exists but is empty |
| `ID_DIR_MISMATCH` | warning | frontmatter `name` does not match the containing directory |

Each finding carries a `witness` path relative to the repository, so a reviewer can open the exact artifact instead of re-deriving the walk.

What it does **not** do: it does not run the upstream CLI, does not validate guide prose, does not judge whether a guide is good, and does not modify any file.

## Install

Python 3.8+ only. No third-party packages, no network access, no build step.

```bash
git clone git@github.com:linmoxi33/mwg-guide-reach.git
cd mwg-guide-reach
```

## Usage

```bash
python3 bin/mwg-guide-reach <repo-root>
python3 bin/mwg-guide-reach <repo-root> --json
python3 bin/mwg-guide-reach <repo-root> --fail-on warning
```

On the bundled broken fixture:

```bash
python3 bin/mwg-guide-reach examples/in/broken
```

```text
mwg-guide-reach 1.0.0
contract: guides/<category>/<guide>/guide.md (depth 2)
guide.md: 6 total, 5 reachable, 1 unreachable
ERROR STUB_DEMO guides/css/empty-demo/guide.md -> guides/css/empty-demo/demo.html: demo.html has no content outside HTML comments and the guide has no targets/
WARNING STUB_EXPECTATIONS guides/css/empty-demo/guide.md -> guides/css/empty-demo/expectations.md: expectations.md exists but is empty
WARNING ID_DIR_MISMATCH guides/css/wrong-name/guide.md -> other-name: frontmatter name 'other-name' differs from directory 'wrong-name'
ERROR DUPLICATE_GUIDE_ID guides/performance/lazy-image/guide.md -> guides/performance/lazy-image/variant/guide.md: guide id 'lazy-image' is declared by 2 files; the inventory map keeps only one
WARNING ID_DIR_MISMATCH guides/performance/lazy-image/variant/guide.md -> lazy-image: frontmatter name 'lazy-image' differs from directory 'variant'
ERROR UNREACHABLE_GUIDE guides/performance/lazy-image/variant/guide.md -> guides/performance/lazy-image/variant: guide.md sits 3 directory level(s) below guides/, contract depth is 2; scanAllGuides() never descends here
3 error(s), 3 warning(s)
```

`--json` output (abridged; full expected output in `examples/out/broken.json`):

```json
{
  "contract": {"depth": 2, "reachable_pattern": "guides/<category>/<guide>/guide.md"},
  "findings": [
    {
      "detail": "guide.md sits 3 directory level(s) below guides/, contract depth is 2; scanAllGuides() never descends here",
      "path": "guides/performance/lazy-image/variant/guide.md",
      "rule": "UNREACHABLE_GUIDE",
      "severity": "error",
      "witness": "guides/performance/lazy-image/variant"
    }
  ],
  "summary": {"errors": 3, "guide_md_total": 6, "reachable": 5, "unreachable": 1, "warnings": 3},
  "tool": "mwg-guide-reach",
  "version": "1.0.0"
}
```

The JSON contains no timestamps or absolute paths derived from the machine, so two runs on the same tree are byte-identical (verified: `sha256` of two runs is `d71c0c53…e1ddc`).

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | no finding at or above `--fail-on` (default: errors only) |
| `1` | at least one finding at or above the threshold |
| `2` | usage error or input error (missing root, no `guides/` directory) |

## Real-corpus result

Run against a sparse checkout of `GoogleChrome/modern-web-guidance-src` at `main` (2026-11-12), only `guides/` materialised:

```bash
git clone --depth=1 --filter=blob:none --sparse \
  git@github.com:GoogleChrome/modern-web-guidance-src.git /tmp/mwg
cd /tmp/mwg && git sparse-checkout set guides
python3 bin/mwg-guide-reach /tmp/mwg --json
```

Measured output (not an estimate):

- **252** `guide.md` files on disk, **251 reachable**, **1 unreachable**
- **2 errors, 1 warning** in 0.062 s
- the single unreachable artifact is `guides/performance/deliver-optimized-decorative-images/serve-alternative-image-formats/guide.md`
- it declares `name: deliver-optimized-decorative-images`, the same id as its parent
- its `expectations.md` is 0 bytes and its `demo.html` contains only `<!-- TODO -->`
- the only warning is the nested directory/id mismatch (`ID_DIR_MISMATCH`), which is a symptom of the same artifact

So the 15.5% figure sometimes quoted for “unvalidated guides” is not what this measures: the measured blind spot is **1 of 252 files (0.40%)**, and that one file happens to be a complete stub. The audit is deliberately narrow rather than inflating the number.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

18 stdlib tests, all green: 9 behaviour tests drive the CLI as a subprocess and assert exit codes, JSON shape and exact expected reports; the rest cover rule classification, determinism and input errors.

## Limitations

- The contract depth (2) is hard-coded to the current `scanAllGuides()` implementation; if upstream starts recursing, this tool will report a stale contract rather than silently following it.
- Frontmatter parsing covers the top-level `name:` scalar only. It does not implement YAML, anchors, or multi-line values.
- A `targets/` or `tasks/` directory suppresses `STUB_DEMO` because upstream accepts either as runnable evidence; the tool does not inspect whether the target itself passes.
- The real-corpus numbers above come from a sparse checkout (only `guides/`), which is exactly the input this tool reads, but they are a snapshot of `main` on 2026-11-12, not a live guarantee.
- No auto-fix: the fix (reject nested guide directories, or make the inventory recurse) belongs upstream.

## 与同类项目的差异 / difference from existing work

Upstream already ships `guides-integrity.test.ts`, but it validates only the guides it can reach; by construction it cannot report an artifact that `scanAllGuides()` never returns. Searches for an independent reachability checker (`gh search repos "modern-web-guidance"`, `gh search code "scanAllGuides"`) found no third-party tool. This project is not a fork and shares no code with upstream; it re-implements the directory contract from the public source and compares it against the filesystem.

## 本轮创新

First measurement of the Modern Web Guidance inventory's **reachability** as a separate property from validity: existing checks answer “is this guide valid”, this tool answers “is this guide even visible to the validator”, and it proves the distinction on the real corpus with one invisible stub that duplicates its parent's id. Other audits in this account check file formats or schema diffs; none measures whether the artifact is reachable by the producer's own enumerator.

## License

MIT. See `LICENSE`.
