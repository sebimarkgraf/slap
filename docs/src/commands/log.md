# shut log

The `shut log` command can be used to manage changelog files which are usually stored in a `.changelog/` directory,
but the directory can be changed using the `tool.shut.changelog-dir` option. The CLI allows you to add new entries
as well as print them in a pretty format in the terminal or render the changelog as Markdown.

A changelog entry has a unique ID, one or more tags that categorize the type of change, one or more authors,
a short description, maybe a link to a pull request and links to issues that are fixed by the change.

```toml
$ shut log add -t fix,docs -m 'Fix the documentation' --fixes 231,234
# Added changelog entry to .changelog/_unreleased.toml
id = "d0092ba"
tags = [ "fix", "docs" ]
message = "Fix the documentation"
fixes = [
  "https://github.com/username/repo/issues/231",
  "https://github.com/username/repo/issues/234",
]
pr = null
```

The `pr` value can be set manually once a PR was created, or be updated automatically for example through a GitHub
action or other type of CI job (the `shut log inject-pr-url` command can help with that).

## Configuration

### `log.directory`

__Type__: `str`
__Default__: `.changelog/`

The directory in which the changelogs are stored.

### `log.valid-types`

__Type__: `list[str]`
__Default__: `["breaking change", "docs", "feature", "fix", "hygiene", "improvement", "tests"]

A list of strings that are accepted in changelog entries as types.

### `log.remote`

__Type__: `RemoteProvider | None`
__Default__: `None`

If `None`, will be automatically detected using the `RemoteDetectorPlugin` plugins.