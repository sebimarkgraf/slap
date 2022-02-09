# shut check

The `shut check` command performs sanity checks on your project.

## Configuration

### `check.plugins`

__Type__: `list[str]`  
__Default__: `["log", "poetry", "release", "shut"]`

A list of check plugins to use. Note that the Poetry plugin will only fire checks if your project appears to be using
Poetry, so there is no harm in leaving it enabled even if you don't use it.

Additional plugins can be registered via an `ApplicationPlugin` under the `CheckPlugin` group.

__Todo__: Error if a specified plugin does not exist.

## Built-in checks

### `log`

The `ChangelogConsistencyCheck` checks if the changelogs managed by Shut are in order.

##### `log:validate`

Checks if all structured changelog files managed by Shut can be loaded and are valid.

---

### `shut`

> The `ShutChecksPlugin` provides all Python specific checks.

##### `shut:packages`

Checks if Shut can detect at least one package.

##### `shut:typed`

Checks if the project is typed but does not contain a `py.typed` file or the other way round.
This currently relies on the `$.typed` configuration and does not inspect the code for type hints.

---

### `poetry`

> The `PoetryChecksPlugin` will perform some Poetry specific configuration checks.

##### `poetry:readme`

Checks if the project readme is configured correctly or if Poetry is able to automatically
pick up the readme file if it is not configured. This inspects te `[tool.poetry.readme]` or `[project.readme]`
settings in `pyproject.toml` and compares it with the readme file that was automatically identified by Shut
(which is a file called README, case-insensitive with one of the suffixes in the order of `.md`, `.rst`, `.txt`,
or if that does not match, any file beginning with `README.`).

##### `poetry:urls`

Checks if the `homepage` key is set in `[tool.poetry]`, __TODO__ Also warn for missing issue and
documentation URL

##### `poetry:classifiers`

__TODO__ Check if all classifiers in `[tool.poetry.classifiers]` are valid.

##### `poetry:license`

__TODO__ Check if the license is a valid SPDX license identifier.

> __Todo__: More of those checks should also support looking into `[project]`.

---

### `release`

> The `ReleaseChecksPlugin` performs checks to validate that `shut release` can be used properly.

##### `release:version`

Checks if the `__version__` can be detected in the source code of all detected packages.

##### `release:remote`

__TODO__ Checks if the VCS remote is configured or can be detected automatically such that the
`shut release --create-release` option can be used.