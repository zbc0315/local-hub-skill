import click

from hub.verbs.reads import list_, show, search, plan_add
from hub.verbs.writes import reindex, add, download, verify, rm
from hub.verbs.add_version import add_version
from hub.verbs.pull import pull


@click.group()
@click.version_option(package_name="hub-cli")
def cli() -> None:
    """Local/LAN open-source dataset ledger."""


cli.add_command(list_)
cli.add_command(show)
cli.add_command(search)
cli.add_command(plan_add)
cli.add_command(reindex)
cli.add_command(add)
cli.add_command(download)
cli.add_command(verify)
cli.add_command(rm)
cli.add_command(add_version)
cli.add_command(pull)


if __name__ == "__main__":
    cli()
