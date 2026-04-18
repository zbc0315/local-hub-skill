import click


@click.group()
@click.version_option(package_name="hub-cli")
def cli() -> None:
    """Local/LAN open-source dataset ledger."""


if __name__ == "__main__":
    cli()
