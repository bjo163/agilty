# ROCKSOUL Release Integrity

## Current packaging authority

`main` currently uses `setup.py`/setuptools as the package metadata and console-script source. The prior ROCKSOUL snapshot used `pyproject.toml` with `uv_build`, but that file is intentionally not restored because it would change the repository's Python floor and packaging backend independently of the current g4f runtime.

The existing upstream PyPI workflow remains repository-gated to `xtekky/gpt4free`. This fork must not claim that workflow publishes `bjo163/agilty`.

## Release policy

- Stage 2 restores source modules, offline tests, product documentation, and non-publishing verification workflows only.
- No ROCKSOUL release workflow, tag creation, GitHub release publication, or PyPI publication is enabled by this recovery.
- A future release migration must define one authoritative version source, align release notes, verify built wheel/sdist metadata, and pass the complete current-main test matrix before publishing.
- Existing tags and GitHub Releases are historical records and must remain immutable; do not rewrite them to make the recovered source appear previously shipped.

## Required release gate

Before a new ROCKSOUL release: run the general repository Unittest, ROCKSOUL CI, Mesh CI, Arena CI, package build, and a metadata/version consistency check on the exact final `main` commit. The release must be a separate, explicitly authorized action.
