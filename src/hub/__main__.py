import click

from hub.verbs.reads import list_, show, search, plan_add
from hub.verbs.writes import reindex


@click.group()
@click.version_option(package_name="hub-cli")
def cli() -> None:
    """Local/LAN open-source dataset ledger."""


cli.add_command(list_)
cli.add_command(show)
cli.add_command(search)
cli.add_command(plan_add)
cli.add_command(reindex)


if __name__ == "__main__":
    cli()
