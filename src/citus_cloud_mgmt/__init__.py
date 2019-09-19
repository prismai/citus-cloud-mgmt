import logging as _logging
import pathlib as _pathlib
import pickle as _pickle
import typing as _tp
from dataclasses import dataclass as _dataclass

import atomicwrites as _atomicwrites
import bs4 as _bs4
import nacl.pwhash as _nacl_pwhash
import nacl.secret as _nacl_secret
import nacl.utils as _nacl_utils
import pyotp as _pyotp
import requests as _requests

try:
    __version__ = __import__("pkg_resources").get_distribution(__name__).version
except:  # noqa # pragma: no cover
    pass

APPNAME = __name__
APPAUTHOR = "Kyrylo Shpytsya"


_logger = _logging.getLogger(__name__)


def citus_console_url(path: str) -> str:
    return f"https://console.citusdata.com/{path}"


SIGNIN_URL = citus_console_url("users/sign_in")
FORMATIONS_URL = citus_console_url("formations")

_PWHASH = _nacl_pwhash.scrypt


@_dataclass
class RoleInfo:
    name: str
    id_: str


class CitusCloudMgmt:
    logged_in: bool
    user: str
    password: str
    totp_secret: str
    cookies_path: _tp.Optional[_pathlib.Path]

    def __init__(
        self,
        *,
        user: str,
        password: str,
        totp_secret: str,
        cookies_path_prefix: _tp.Optional[str] = None,
    ) -> None:
        self.logged_in = False
        self.user = user
        self.password = password
        self.totp_secret = totp_secret

        if cookies_path_prefix is None:
            self.cookies_path = None
        else:
            self.cookies_path = _pathlib.Path(cookies_path_prefix + user)

        self._session = _requests.Session()
        self._load_cookies()

    def _secret_box(self, salt: bytes) -> _nacl_secret.SecretBox:
        assert len(salt) == _PWHASH.SALTBYTES
        key = _PWHASH.kdf(
            _nacl_secret.SecretBox.KEY_SIZE,
            b''.join(i.encode() for i in [self.password, self.totp_secret]),
            salt,
            opslimit=_PWHASH.OPSLIMIT_INTERACTIVE,
            memlimit=_PWHASH.MEMLIMIT_INTERACTIVE,
        )
        return _nacl_secret.SecretBox(key)

    def _load_cookies(self) -> None:
        if self.cookies_path and self.cookies_path.exists():
            xblob = self.cookies_path.read_bytes()

            salt = xblob[:_PWHASH.SALTBYTES]
            box = self._secret_box(salt)
            blob = box.decrypt(xblob[_PWHASH.SALTBYTES:])

            jar = _pickle.loads(blob)
            self._session.cookies.update(jar)
            _logger.debug("Loaded cookies from %s", self.cookies_path)

    def _save_cookies(self) -> None:
        if self.cookies_path:
            blob = _pickle.dumps(self._session.cookies)

            salt = _nacl_utils.random(_PWHASH.SALTBYTES)
            box = self._secret_box(salt)
            xblob = salt + box.encrypt(blob)

            with _atomicwrites.atomic_write(
                str(self.cookies_path),
                mode="wb",
                overwrite=True,
            ) as f:
                f.write(xblob)

            _logger.debug("Saved cookies to %s", self.cookies_path)

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: _tp.Optional[_tp.Dict[str, str]] = None,
        params: _tp.Optional[_tp.Dict[str, str]] = None,
        json: _tp.Any = None,
    ) -> _requests.Response:
        url = citus_console_url(path)

        while True:
            r = self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
            )
            r.raise_for_status()

            if r.url == url:
                self._save_cookies()
                return r

            if r.url == SIGNIN_URL:
                _logger.debug("Signing into Citus Console")

                soup = _bs4.BeautifulSoup(r.text, "html.parser")
                form = soup.find("form", {"id": "new_user"})
                assert form

                signin_params = {}

                for i in form.find_all("input", {"type": "hidden"}):
                    signin_params[i.attrs["name"]] = i.attrs["value"]

                signin_params["user[email]"] = self.user
                signin_params["user[password]"] = self.password

                #######################################################################

                r = self._session.post(SIGNIN_URL, params=signin_params)
                r.raise_for_status()

                if not r.url.startswith(SIGNIN_URL + "?"):
                    raise RuntimeError(f"Unexpected redirect from sign-in #1 to {r.url}")

                soup = _bs4.BeautifulSoup(r.text, "html.parser")
                assert soup.find("div", {"data-react-class": "TwoFAWidget"})

                auth_token = soup.find("meta", {"name": "csrf-token"}).attrs["content"]

                signin_params = {}
                signin_params["user[otp_attempt]"] = _pyotp.TOTP(self.totp_secret).now()
                signin_params["authenticity_token"] = auth_token

                #######################################################################

                _logger.debug("Sending 2FA token")

                r = self._session.post(SIGNIN_URL, params=signin_params)
                r.raise_for_status()

                if r.url == FORMATIONS_URL or r.url == url:
                    _logger.debug("Successfully signed into Citus Console")
                    continue

                raise RuntimeError(f"Unexpected redirect from sign-in #2 to {r.url}")
            else:
                raise RuntimeError(f"Unexpected redirect to {r.url}")

    def login(self) -> None:
        self._request("get", "formations")

    def _get_csrf_token(
        self,
        path: str,
    ) -> str:
        r = self._request("get", path, headers={"Accept": "text/html"})
        soup = _bs4.BeautifulSoup(r.text, "html.parser")
        result = soup.find("meta", {"name": "csrf-token"}).attrs["content"]
        assert isinstance(result, str)
        return result

    def list_roles(
        self,
        formation: str,
    ) -> _tp.List[RoleInfo]:
        path = f"formations/{formation}"
        self._get_csrf_token(path)

        r = self._request("get", path, headers={"Accept": "application/json"})
        data = r.json()
        return [
            RoleInfo(name=i["name"], id_=i["id"])
            for i in data["roles"]
        ]

    def create_role(
        self,
        formation: str,
        name: str,
    ) -> str:
        path = f"formations/{formation}/roles"
        auth_token = self._get_csrf_token(path)

        r = self._request(
            "post",
            path,
            json={"role_name": name},
            headers={"Accept": "application/json", "X-CSRF-Token": auth_token},
        )

        data = r.json()
        result = data["id"]
        assert isinstance(result, str)

        if result == "conflict":
            raise RuntimeError(f"Role named \"{name}\" already exists")

        assert data["name"] == name
        return result

    def delete_role(
        self,
        formation: str,
        id_: str,
    ) -> None:
        path = f"formations/{formation}"
        auth_token = self._get_csrf_token(path)

        self._request(
            "delete",
            f"{path}/roles/{id_}",
            headers={"X-CSRF-Token": auth_token},
        )

    def get_role_credentials(
        self,
        formation: str,
        id_: str,
    ) -> str:
        path = f"formations/{formation}/roles/{id_}/credentials"

        r = self._request("get", path)

        soup = _bs4.BeautifulSoup(r.text, "html.parser")
        body = soup.find("body")
        assert body
        assert len(body.contents) == 1
        assert isinstance(body.contents[0], _bs4.element.NavigableString)

        return _tp.cast(str, body.contents[0].strip())
