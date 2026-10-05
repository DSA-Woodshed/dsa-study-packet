# Shared contribution hooks

The five executable files mirror `DSA-Woodshed/.github/githooks` byte-for-byte.
The Just mirror is pinned to governance commit
`7e217e4817a61545a8564845b3f4b77a04e5b548`. They derive from `Great-Falls-Tool-Bus/.github` commit
`7a4702fdb6bbeb99c4387d09f48cba096857c9ca`, adapted for the DSA Woodshed owner.
The fixture tests preserve the operator's HOME and isolate Git configuration
through `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_NOSYSTEM`.

Use `just hooks-install`, `just hooks-check`, and `just hooks-test`.
`just hooks-check file:///absolute/path/to/mirror/githooks` supports an offline
fixture. The checks cover fork-first pushes, authored signatures, semantic
naming, commit-message attribution, and chaining the global hook layer.
Personal agent hooks and provider settings belong on contribution overlays.
