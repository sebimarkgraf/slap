
import click
import networkx as nx

from shut.commands.pkg.install import collect_requirement_args, run_install, split_extras
from shut.model.monorepo import MonorepoModel
from . import mono, project


@mono.command()
@click.option('--develop/--no-develop', default=True, help='Install in develop mode (default: true)')
@click.option('--dev/--no-dev', default=None, help='Install dev requirements (default: as per --develop/--no-develop)')
@click.option('--test/--no-test', default=None, help='Install test requirements (default: as per --develop/--no-develop)')
@click.option('--extra', type=split_extras, help='Specify one or more extras to install.')
@click.option('-U', '--upgrade', is_flag=True, help='Upgrade all packages (forwarded to pip install).')
@click.option('-q', '--quiet', is_flag=True, help='Quiet install')
@click.option('--pip', help='Override the command to run Pip. Defaults to "python -m pip" or the PIP variable.')
@click.option('--pip-args', help='Additional arguments to pass to Pip.')
@click.option('--dry', is_flag=True, help='Print the Pip command to stdout instead of running it.')
def install(develop, dev, test, extra, upgrade, quiet, pip, pip_args, dry):
  """
  Install all packages in the monorepo using`python -m pip`.

  The command used to invoke Pip can be overwritten using the `PIP` environment variable.
  """

  monorepo = project.load_or_exit(expect=MonorepoModel)
  graph = monorepo.get_inter_dependencies_graph()
  package_map = {p.name: p for p in project.packages}

  if extra is None: extra = []
  if dev is None: dev = develop
  if test is None: test = develop
  if dev: extra += ['dev']
  if test: extra += ['test']

  args = []
  for package_name in nx.algorithms.dag.topological_sort(graph):
    package = package_map[package_name]
    args += collect_requirement_args(package, develop, False, extra)
    args += package.install.get_pip_args()

  if pip_args:
    args += shlex.split(pip_args)

  run_install(pip, args, upgrade, quiet, dry)
