
from __future__ import annotations

import dataclasses
from multiprocessing.sharedctypes import Value
import sys
import typing as t
from pathlib import Path

from databind.core.annotations import alias

from slam.application import Application, Command, argument, option
from slam.plugins import ApplicationPlugin, ReleasePlugin, VersionIncrementingRulePlugin

if t.TYPE_CHECKING:
  from poetry.core.semver.version import Version  # type: ignore[import]
  from slam.project import Project
  from slam.release import VersionRef


@dataclasses.dataclass
class VersionRefConfig:
  file: str
  pattern: str


@dataclasses.dataclass
class ReleaseConfig:
  #: The VCS branch on which releases are allowed. The release command will prevent you from creating a release
  #: while on a different branch (unless `--no-branch-check` is set).
  branch: str = 'develop'

  #: The template for the commit message when a release is created and the `--tag, -t` option is used.
  commit_message: t.Annotated[str, alias('commit-message')] = 'release {version}'

  #: The template for the tag name when a release is created and the `--tag, -t` option is used.
  tag_format: t.Annotated[str, alias('tag-format')] = '{version}'

  #: A list of references to the version number that should be updated along with the version numbers
  #: that the release command knows about by default (like the `version` in `pyproject.toml` and the
  #: version number in the source code).
  references: list[VersionRefConfig] = dataclasses.field(default_factory=list)

  #: A list of {@link ReleasePlugin}s to use. Defaults to contain the {@link SourceCodeVersionReferencesPlugin}
  #: and {@link ChangelogReleasePlugin}.
  plugins: list[str] = dataclasses.field(default_factory=lambda: ['source_code_version', 'changelog_release'])


class ReleaseCommandPlugin(Command, ApplicationPlugin):
  """ Create a new release of your Python package.

  This command can perform the following operations in sequence (most of them need
  to be enabled explicitly with flags):

  1. Bump the version number in <u>pyproject.toml</u> and in other files
  2. Add the changed files to Git, create a commit and a tag (<opt>--tag, -t</opt>)
  3. Push the commit and tag to the remote repository (<opt>--push, -p</opt>)
  4. Create a new release on the repository host (eg. <u>GitHub</u>) (<opt>--create-release, -R</opt>)

  In addition to the <u>pyproject.toml</u>, the command will automatically detect the file(s)
  in your Python source code that contain a <b>__version__</b> member and update it as well.
  Additional files can be updated by configuring the <fg=green>[tool.slam.release.references]</fg>
  option:

    <fg=green>[tool.slam.release]</fg>
    <fg=dark_gray>references</fg> = [
      {{ <fg=dark_gray>file</fg> = <fg=yellow>"../frontend/package.json"</fg>, <fg=dark_gray>pattern</fg> = <fg=yellow>"  \\"version\\": \\"{{VERSION}}\\""</fg> }}
    ]

  Furthermore, the <opt>--validate</opt> option can be used in CI to ensure that the version
  numbers are consistent across the project. This is particularly useful when
  automating publishing from CI builds.

  <b>Bumping the version number</b>

    Specifying an explicit version number or a version bump rule for the <opt>version</opt>
    argument will update the version across all references that can be detected.
    You can use <opt>--validate</opt> to show all files in which version numbers are found.

    The supported rules are <u>major</u>, <u>premajor</u>, <u>minor</u>, <u>preminor</u>, <u>patch</u>, <u>prepatch</u> and
    <u>prerelease</u>.

    <u>[Git]</u>: The command will prevent you from bumping the version unless you are on
    the branch configured under <fg=green>[tool.slam.release.branch]</fg> or "develop" by default.
    If you want to skip that check, pass <opt>--no-branch-check</opt>.

  <b>Commit & tag</b>

    <u>[Git]</u>: You can use the <opt>--tag, -t</opt> flag to automatically add the updated files,
    create a new commit and tag the commit with the version number. The tag name
    by default will just be the version number, but can be changed by setting the
    <fg=green>[tool.slam.release.tag_format]</fg>. Similarly, the commit message used can be
    configured with <fg=green>[tool.slam.release.commit_message]</fg>.

  <b>Push to remote</b>

    <u>[Git]</u>: Using the <opt>--push, -p</opt> in combination with <opt>--tag, -t</opt> will push the new
    commit and tag to the remote Git repository immediately. You can specify the
    <opt>--remote, -r</opt> option to change the remote which will be pushed to (defaults
    to "origin").

  <b>Create a release</b>

    You can use the <opt>--create-release, -R</opt> flag to enable creating a release on the
    repository hosting service. The following hosting services are supported and
    can be automatically detected or explicitly configured.

    If you make use of changelogs, the changelog contents will be included in the
    release description.

    <u>[GitHub]</u>: Creates a GitHub release on the repository. Automatically detected
    for repositories that have a <u>github.com</u> "origin" remote. Otherwise, it can be
    configured like this:

      <fg=green>[tool.slam.remote]</fg>
      <fg=dark_gray>type</fg> = <fg=yellow>"github"</fg>
      <fg=dark_gray>repo</fg> = <fg=yellow>"my-github-enterprise.com/owner/repo"</fg>

  <b>Environment variables</b>

    <u>SLAM_RELEASE_NO_PLUGINS</u>: If set, no release plugins will be loaded besides the builtin.
  """

  app: Application
  config: dict[Project, ReleaseConfig]

  name = "release"
  arguments = [
    argument("version", "The target version number or rule to apply to the current version.", True),
  ]
  options = [
    option("tag", "t", "Create a Git tag after the version numbers were updated."),
    option("push", "p", "Push the changes to the Git remote repository."),
    option("create-release", "R", "Create a release on the repository service (e.g. GitHub)."),
    option("remote", "r", "The Git remote to push to (only when <opt>--push</opt> is specified).", False),
    option("dry", "d", "Do not commit changes to disk."),
    option("force", "f", "Force tag creation and push."),
    option("validate", None, "Instead of bumping the version, validate that all version references are consistent.\n"
      "If the <opt>version</opt> argument is specified, all version references must match it."),
    option("no-branch-check", None, "Do not validate the current Git branch matches the configured release branch."),
    option("no-worktree-check", None, "Do not check the worktree state."),
  ]

  # TODO (@NiklasRosenstein): Support "git" rule for bumping versions

  def load_configuration(self, app: Application) -> dict[Project, ReleaseConfig]:
    import databind.json
    result = {}
    for project in app.projects:
      data = project.raw_config().get('release', {})
      result[project] = databind.json.load(data, ReleaseConfig)
    self.app = app
    self.config = result
    return result

  def activate(self, app: Application, config: dict[Project, ReleaseConfig]) -> None:
    app.cleo.add(self)

  def _validate_options(self) -> int:
    """ Internal. Ensures that the combination of provided options make sense. """

    if self.option("dry") and self.option("validate"):
      self.line_error('error: <opt>--dry</opt> cannot be combined with <opt>--validate</opt>', 'error')
      return 1
    if self.option("tag") and self.option("validate"):
      self.line_error('error: <opt>--tag</opt> cannot be combined with <opt>--validate</opt>', 'error')
      return 1
    if self.option("push") and not self.option("tag"):
      self.line_error('error: <opt>--push</opt> can only be combined with <opt>--tag</opt>', 'error')
      return 1
    if self.option("force") and not self.option("tag"):
      self.line_error('error: <opt>--force</opt> can only be combined with <opt>--tag</opt> and <opt>--push</opt>', 'error')
      return 1
    if self.option("remote") is not None and not self.option("push"):
      self.line_error('error: <opt>--remote</opt> can only be combined with <opt>--push</opt>', 'error')
      return 1

    self.io.input.set_option("remote", self.option("remote") or "origin")

    if self.option("tag") and not self.is_git_repository:
      self.line_error('error: not in a git repository, cannot use <opt>--tag</opt>', 'error')
      return 1
    if self.option("push") and not self.is_git_repository:
      self.line_error('error: not in a git repository, cannot use <opt>--push</opt>', 'error')
      return 1
    if self.option("push") and (remote := self.option("remote")) not in {r.name for r in self.git.remotes()}:
      self.line_error(f'error: git remote "{remote}" does not exist', 'error')
      return 1

    return 0

  def _load_plugins(self, project: Project) -> list[ReleasePlugin]:
    """ Internal. Loads the plugins for the given project. """

    from nr.util.plugins import load_entrypoint

    plugins = []
    for plugin_name in self.config[project].plugins:
      plugin = load_entrypoint(ReleasePlugin, plugin_name)()
      plugin.app = self.app
      plugin.io = self.io
      plugins.append(plugin)
    return plugins

  def _show_version_refs(self, version_refs: list[VersionRef], increment_to: str | None = None) -> None:
    """ Internal. Prints the version references to the terminal. """

    max_w1 = max(len(str(ref.file)) for ref in version_refs) + 1
    max_w2 = max(len(ref.value) for ref in version_refs)
    prev: VersionRef | None = None
    for ref in sorted(version_refs, key=lambda r: r.file):
      filename = str(ref.file) + ':' if not prev or prev.file != ref.file else ''
      self.io.write(f'  <fg=cyan>{(filename).ljust(max_w1)}</fg> {ref.value.ljust(max_w2)}')
      if increment_to:
        self.io.write(f' → <b>{increment_to}</b>')
      self.io.write_line(f' <fg=dark_gray># {ref.content}</fg>')
      prev = ref

  def _validate_version_refs(self, version_refs: list[VersionRef], version: str | None) -> int:
    """ Internal. Verifies the consistency of the given version references. This is used when `--validate` is set. """

    from poetry.core.semver.version import Version

    if version is not None:
      Version.parse(version)

    versions = set(ref.value for ref in version_refs)
    if not versions:
      self.line(f'<info>no version numbers detected</info>')
      return 1

    if len(versions) > 1:
      self.line('<error>versions are inconsistent</error>')
      self._show_version_refs(version_refs)
      return 1

    has_version = next(iter(versions))
    if version is not None:
      if version != has_version:
        self.line(f'<error>version mismatch, expected <b>{version}</b>, got <b>{has_version}</b></error>')
        return 1

    self.line(f'<comment>versions are ok</comment>')
    self._show_version_refs(version_refs)
    return 0

  def _check_on_release_branch(self) -> bool:
    """ Internal. Checks if the current Git branch matches the configured release branch. """

    from nr.util.git import NoCurrentBranchError

    if not self.is_git_repository or self.option("no-branch-check"):
      return True

    config = self.config[self.app.root_project()]

    try:
      current_branch = self.git.get_current_branch_name()
    except NoCurrentBranchError:
      self.line_error(f'error: not currently on a Git branch', 'error')
      return False

    if current_branch != config.branch:
      self.line_error(
        f'error: current branch is <b>{current_branch}</b> but must be on the '
          f'release branch (<b>{config.branch}</b>)', 'error'
      )
      return False
    return True

  def _check_clean_worktree(self, required_files: list[Path]) -> bool:
    """ Internal. Checks that the Git work state is clean and that all the *required_files* are tracked in the repo. """

    if not self.is_git_repository or self.option("no-worktree-check"):
      return True

    queried_files = {f.resolve() for f in required_files}
    tracked_files = {Path(f).resolve() for f in self.git.get_files()}
    if (untracked_files := queried_files - tracked_files):
      self.line_error('error: some of the files with version references are not tracked by Git', 'error')
      for fn in untracked_files:
        self.line_error(f'  · {fn}', 'error')
      return False

    file_status = list(self.git.get_status())
    if any(f.mode[1] != ' ' for f in file_status):
      self.line_error('error: found untracked changes in worktree', 'error')
      return False
    if any(f.mode[0] not in ' ?' for f in file_status):
      self.line(
        '<fg=yellow>found modified files in the staging area. these files will be committed into the release tag.</fg>'
      )
      if not self.confirm('continue?'):
        return False

    return True

  def _get_current_version(self, version_refs: list[VersionRef]) -> 'Version':
    """ Try to identify the current version number among the version refs. This is done by selecting all versions
    that occur in a `pyproject.toml`, and if they are all equal, they are considered the current version. If they
    are different, a {@link ValueError} is raised. """

    from poetry.core.semver.version import Version

    current_version = {r.value for r in version_refs if r.file.name == 'pyproject.toml'}
    if len(current_version) != 1:
      raise ValueError('could not determine current version number')

    return Version.parse(next(iter(current_version)))

  def _get_new_version(self, version_refs: list[VersionRef], rule: str) -> 'Version':
    """ Return the new version, based on *rule*. If *rule* is a version string, it is used as the new version.
    Otherwise, it is considered a rule and the applicable rule plugin is invoked to construct the new version. """

    from poetry.core.semver.version import Version
    from nr.util.plugins import load_entrypoint, NoSuchEntrypointError

    try:
      return Version.parse(rule)
    except ValueError:
      try:
        plugin = load_entrypoint(VersionIncrementingRulePlugin, rule)
      except NoSuchEntrypointError:
        self.line(f'error: "<b>{rule}</b>" is not a valid version incrementing rule', 'error')
        sys.exit(1)
      return plugin().increment_version(self._get_current_version(version_refs))

  def _bump_version(self, version_refs: list[VersionRef], target_version: Version, dry: bool) -> list[Path]:
    """ Internal. Replaces the version reference in all files with the specified *version*. """

    from nr.util import Stream
    from nr.util.text import substitute_ranges

    self.line(
      f'bumping <b>{len(version_refs)}</b> version reference{"" if len(version_refs) == 1 else "s"} to '
      f'<b>{target_version}</b>'
    )

    changed_files: list[Path] = []

    self._show_version_refs(version_refs, target_version)
    self.line('')
    for filename, refs in Stream(version_refs).groupby(lambda r: r.file):
      with open(filename) as fp:
        content = fp.read()

      content = substitute_ranges(
        content,
        ((ref.start, ref.end, str(target_version)) for ref in refs),
      )

      changed_files.append(filename)
      if not dry:
        with open(filename, 'w') as fp:
          fp.write(content)

    for project in self.app.projects:
      for plugin in self._load_plugins(project):
        try:
          changed_files.extend(plugin.create_release(project, str(target_version), dry))
        except:
          self.line_error(f'error with {type(plugin).__name__}.bump_version()', 'error')
          raise

    return changed_files

  def _create_tag(self, target_version: str, changed_files: list[Path], dry: bool, force: bool) -> str:
    """ Internal. Used when --tag is specified to create a Git tag. """

    assert self.is_git_repository

    # TODO (@NiklasRosenstein): If this step errors, revert the changes made by the command so far?

    config = self.config[self.app.root_project()]

    if '{version}' not in config.tag_format:
      self.line_error('<info>tool.slam.release.tag-format<info> must contain <info>{version}</info>', 'error')
      sys.exit(1)
    tag_name = config.tag_format.replace('{version}', str(target_version))
    self.line('')
    self.line(f'tagging <fg=cyan>{tag_name}</fg>')

    if not dry:
      commit_message = config.commit_message.replace('{version}', str(target_version))
      self.git.add([str(f) for f in changed_files])
      self.git.commit(commit_message, allow_empty=True)
      self.git.tag(tag_name, force=force)

    return tag_name

  def _push_to_remote(self, tag_name: str, remote: str, dry: bool, force: bool) -> None:
    """ Internal. Push the current branch and the tag to the remote repository. Use when `--push` is set. """

    assert self.is_git_repository

    branch = self.git.get_current_branch_name()

    self.line('')
    self.line(f'pushing <fg=cyan>{branch}</fg>, <fg=cyan>{tag_name}</fg> to <info>{remote}</info>')

    if not dry:
      self.git.push(remote, branch, tag_name, force=force)

  def _get_version_refs(self) -> list[VersionRef]:
    """ Extracts all version references in the projects controlled by the application and returns them. """

    from slam.release import match_version_ref_pattern

    PYPROJECT_TOML_PATTERN = r'^version\s*=\s*[\'"]?(.*?)[\'"]'

    version_refs = []

    # Understand the version references defined in the project configuration.
    for project in self.app.projects:
      references = self.config[project].references[:]

      # Always consider the version number in the pyproject.toml.
      if project.pyproject_toml.exists():
        pyproject_ref_config = VersionRefConfig(
          str(project.pyproject_toml.path.relative_to(project.directory)),
          PYPROJECT_TOML_PATTERN
        )
        references.insert(0, pyproject_ref_config)

      for config in references:
        pattern = config.pattern.replace('{version}', r'(.*?)')
        version_ref = match_version_ref_pattern(project.directory / config.file, pattern)
        if version_ref is not None:
          version_refs.append(version_ref)

    # Query plugins for additional version references.
    for project in self.app.projects:
      for plugin in self._load_plugins(project):
        version_refs += plugin.get_version_refs(project)

    version_refs.sort(key=lambda r: r.file)

    for ref in version_refs:
      if ref.file == ref.file.absolute():
        ref.file = ref.file.relative_to(Path.cwd())

    return version_refs

  def handle(self) -> int:
    """ Entrypoint for the command."""

    from nr.util import Stream
    from nr.util.git import Git

    self.git = Git()
    self.is_git_repository = self.git.get_toplevel() is not None

    if (err := self._validate_options()) != 0:
      return err

    version_refs = self._get_version_refs()
    version = self.argument("version")

    if self.option("validate"):
      if version is None:
        try:
          version = str(self._get_current_version(version_refs))
        except ValueError:
          pass
      return self._validate_version_refs(version_refs, version)

    if version is not None:
      if self.option("tag") and not self._check_on_release_branch():
        return 1
      if self.option("tag") and not self._check_clean_worktree([x.file for x in version_refs]):
        return 1
      if self.option("dry"):
        self.line('dry mode enabled, no changes will be committed to disk', 'comment')
      target_version = self._get_new_version(version_refs, version)
      changed_files = self._bump_version(version_refs, target_version, self.option("dry"))
      if self.option("tag"):
        tag_name = self._create_tag(target_version, changed_files, self.option("dry"), self.option("force"))
        if self.option("push"):
          self._push_to_remote(tag_name, self.option("remote"), self.option("dry"), self.option("force"))

    else:
      self.line_error(
        '<error>error: no action implied, specify a <info>version</info> argument or the <info>--validate</info> option'
      )
      return 1

    return 0

