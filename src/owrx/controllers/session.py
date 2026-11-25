from owrx.controllers.template import WebpageController
from urllib.parse import parse_qs, urlencode
from uuid import uuid4
from http.cookies import SimpleCookie
from owrx.users import UserList
from owrx.config.core import CoreConfig
from datetime import datetime, timedelta

import json
import os
import stat
import logging

logger = logging.getLogger(__name__)


class SessionStorage(object):
    sharedInstance = None
    sessionLifetime = timedelta(hours=6)

    @staticmethod
    def getSharedInstance():
        if SessionStorage.sharedInstance is None:
            SessionStorage.sharedInstance = SessionStorage()
        return SessionStorage.sharedInstance

    def __init__(self):
        self.sessions = {}
        self._load()

    # Sessions used to live only in memory, so every service restart logged
    # everyone out — and a restart is needed for any change under owrx/. They
    # are now kept on disk. The file holds bearer tokens, so it is written
    # readable by its owner only.

    @staticmethod
    def _getSessionsFile():
        return "{data_directory}/sessions.json".format(data_directory=CoreConfig().get_data_directory())

    def _load(self):
        try:
            with open(SessionStorage._getSessionsFile(), "r") as f:
                stored = json.load(f)
        except FileNotFoundError:
            return
        except Exception:
            logger.exception("error while reading the sessions file")
            return

        now = datetime.utcnow()
        for key, entry in stored.items():
            try:
                expires = datetime.fromisoformat(entry["expires"])
            except Exception:
                continue
            # expired sessions are dropped instead of being revived
            if expires > now:
                self.sessions[key] = (expires, entry["data"])
        if self.sessions:
            logger.info("restored %d session(s) from disk", len(self.sessions))

    def _store(self):
        path = SessionStorage._getSessionsFile()
        try:
            payload = {
                key: {"expires": expires.isoformat(), "data": data}
                for key, (expires, data) in self.sessions.items()
            }
            with open(path, "w") as f:
                json.dump(payload, f)
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            logger.exception("error while writing the sessions file")

    def generateKey(self):
        return str(uuid4())

    def startSession(self, data):
        key = self.generateKey()
        self.updateSession(key, data)
        self._store()
        return key

    def endSession(self, key):
        if key in self.sessions:
            del self.sessions[key]
            self._store()

    def getSession(self, key):
        if key not in self.sessions:
            return None
        expires, data = self.sessions[key]
        if expires < datetime.utcnow():
            del self.sessions[key]
            self._store()
            return None
        return data

    def updateSession(self, key, data):
        expires = datetime.utcnow() + SessionStorage.sessionLifetime
        self.sessions[key] = expires, data

    def prolongSession(self, key):
        data = self.getSession(key)
        if data is None:
            raise KeyError("Invalid session key")
        # deliberately not written to disk: this runs on every page load, and
        # rewriting the file each time would hammer the SD card. The session
        # keeps the expiry it had when it was created.
        self.updateSession(key, data)


class SessionController(WebpageController):
    def loginAction(self):
        self.serve_template("login.html", **self.template_variables())

    def processLoginAction(self):
        data = parse_qs(self.get_body().decode("utf-8"))
        data = {k: v[0] for k, v in data.items()}
        userlist = UserList.getSharedInstance()
        if "user" in data and "password" in data:
            if data["user"] in userlist:
                user = userlist[data["user"]]
                if user.is_enabled() and user.password.is_valid(data["password"]):
                    key = SessionStorage.getSharedInstance().startSession({"user": user.name})
                    cookie = SimpleCookie()
                    cookie["owrx-session"] = key
                    target = self.request.query["ref"][0] if "ref" in self.request.query else "/settings"
                    if user.must_change_password:
                        target = "/pwchange?{0}".format(urlencode({"ref": target}))
                    self.set_response_cookies(cookie)
                    self.send_redirect(target)
                    return
        target = "{}login?{}".format(self.get_document_root(), urlencode({"ref": self.request.query["ref"][0]}))
        self.send_redirect(target)

    def logoutAction(self):
        # upstream this was a placeholder that did nothing
        if "owrx-session" in self.request.cookies:
            SessionStorage.getSharedInstance().endSession(self.request.cookies["owrx-session"].value)
        cookie = SimpleCookie()
        cookie["owrx-session"] = ""
        cookie["owrx-session"]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        self.set_response_cookies(cookie)
        self.send_redirect("{0}".format(self.get_document_root() or "./"))
