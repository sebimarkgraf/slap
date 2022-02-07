
import dataclasses
import typing as t

from shut.application import Application
from shut.changelog.changelog_manager import ChangelogManager
from shut.commands.check.api import Check, CheckPlugin


@dataclasses.dataclass
class ChangelogConsistencyCheck(CheckPlugin):

  manager: ChangelogManager

  def get_checks(self, app: Application) -> t.Iterable[Check]:
    yield self._check_changelogs()

  def _check_changelogs(self) -> Check:
    from databind.core import ConversionError

    bad_changelogs = []
    count = 0
    for changelog in self.manager.all():
      count += 1
      try:
        for entry in changelog.load().entries:
          self.manager.validate_entry(entry)
      except (ConversionError, ValueError):
        bad_changelogs.append(changelog.path.name)

    check_name = 'shut:validate-changelogs'
    if not count:
      return Check(check_name, Check.Result.SKIPPED, None)

    return Check(
      check_name,
      Check.ERROR if bad_changelogs else Check.Result.OK,
      f'Broken or invalid changelogs: {", ".join(bad_changelogs)}' if bad_changelogs else
        f'All {count} changelogs are valid.',
    )