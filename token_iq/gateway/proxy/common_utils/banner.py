from typing import Final

# Token IQ ASCII banner
TOKEN_IQ_BANNER: Final = """   ████████╗ ██████╗ ██╗  ██╗███████╗███╗   ██╗    ██╗ ██████╗
   ╚══██╔══╝██╔═══██╗██║ ██╔╝██╔════╝████╗  ██║    ██║██╔═══██╗
      ██║   ██║   ██║█████╔╝ █████╗  ██╔██╗ ██║    ██║██║   ██║
      ██║   ██║   ██║██╔═██╗ ██╔══╝  ██║╚██╗██║    ██║██║▄▄ ██║
      ██║   ╚██████╔╝██║  ██╗███████╗██║ ╚████║    ██║╚██████╔╝
      ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝    ╚═╝ ╚══▀▀═╝

                                       powered by NITCO Inc."""


def show_banner():
    """Display the Token IQ CLI banner."""
    try:
        import click

        click.echo(f"\n{TOKEN_IQ_BANNER}\n")
    except ImportError:
        print("\n")  # noqa: T201
