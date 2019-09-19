import functools
import logging
import typing as tp

import citus_cloud_mgmt
import click
import click_log
import tabulate

from . import CitusCloudMgmt

logger = logging.getLogger(__name__)
click_log.basic_config(logger)
citus_cloud_mgmt._logger = logger


def click_wrapper(wrapper: tp.Callable[..., None], wrapped: tp.Callable[..., None]) -> tp.Callable[..., None]:
    wrapped_params = getattr(wrapped, "__click_params__", [])
    wrapper_params = getattr(wrapper, "__click_params__", [])
    result = functools.update_wrapper(wrapper, wrapped)
    result.__click_params__ = wrapped_params + wrapper_params  # type: ignore
    return result


def base_command(func: tp.Callable[..., None]) -> tp.Callable[..., None]:
    @click_log.simple_verbosity_option(logger)  # type: ignore
    def wrapper(**opts: tp.Any) -> None:
        func(**opts)

    return click_wrapper(wrapper, func)


def client_command(func: tp.Callable[..., None]) -> tp.Callable[..., None]:
    @base_command
    @click.option(
        "--user", "-u",
        envvar="CITUS_CLOUD_USER",
        required=True,
        help="Citus Cloud user email.",
    )
    @click.option(
        "--password", "-p",
        envvar="CITUS_CLOUD_PASSWORD",
        required=True,
        help="Citus Cloud user password.",
    )
    @click.option(
        "--totp", "-t",
        envvar="CITUS_CLOUD_TOTP_SECRET",
        required=True,
        help="Citus Cloud TOTP 2FA secret.",
    )
    @click.option(
        "--cookies",
        help="Prefix for files to store cookies.",
    )
    def wrapper(**opts: tp.Any) -> None:
        client = CitusCloudMgmt(
            user=opts["user"],
            password=opts["password"],
            totp_secret=opts["totp"],
            cookies_path_prefix=opts["cookies"],
        )
        func(client, **opts)

    return click_wrapper(wrapper, func)


def formation_command(func: tp.Callable[..., None]) -> tp.Callable[..., None]:
    @client_command
    @click.option(
        "--formation", "-f",
        envvar="CITUS_CLOUD_FORMATION",
        required=True,
        help="Citus Cloud formation id.",
    )
    def wrapper(
        client: CitusCloudMgmt,
        **opts: tp.Any
    ) -> None:
        func(client, **opts)

    return click_wrapper(wrapper, func)


@click.group()
@click.version_option()
def main(**opts: tp.Any) -> None:
    """
    Tool to manage some of Citus Cloud entities
    """


@main.command(name="login")
@client_command
def main_login(
    client: CitusCloudMgmt,
    **opts: tp.Any
) -> None:
    """
    Verify ability to Citus Cloud.
    """
    client.login()
    logger.info("successfully logged in")


@main.group(name="role")
def main_role(**opts: tp.Any) -> None:
    """
    Manage roles.
    """


@main_role.command(name="list")
@formation_command
def main_role_list(
    client: CitusCloudMgmt,
    **opts: tp.Any
) -> None:
    """
    List roles for given formation.
    """

    roles = client.list_roles(opts["formation"])
    click.echo(
        tabulate.tabulate(
            [{"Name": i.name, "Id": i.id_} for i in roles],
            headers="keys",
        ),
    )


@main_role.command(name="create")
@formation_command
@click.argument("name")
def main_role_create(
    client: CitusCloudMgmt,
    **opts: tp.Any
) -> None:
    """
    Create a new role named NAME for given formation.
    """

    role_id = client.create_role(opts["formation"], opts["name"])
    logger.info(f"Created new role \"name\" with id=\"{role_id}\"")
    click.echo(role_id)


@main_role.command(name="delete")
@formation_command
@click.argument("id")
def main_role_delete(
    client: CitusCloudMgmt,
    **opts: tp.Any
) -> None:
    """
    Delete role with given ID for given formation.
    """

    id_ = opts["id"]
    client.delete_role(opts["formation"], id_)
    logger.info(f"Deleted role with id=\"{id_}\"")


@main_role.command(name="get-cred")
@formation_command
@click.argument("id")
def main_role_get_cred(
    client: CitusCloudMgmt,
    **opts: tp.Any
) -> None:
    """
    Get Postgres credentials for a role with given ID for given formation.
    """

    creds = client.get_role_credentials(opts["formation"], opts["id"])
    click.echo(creds)
