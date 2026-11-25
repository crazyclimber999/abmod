from owrx.controllers.session import SessionStorage
from owrx.users import UserList
from urllib import parse
from http.cookies import SimpleCookie

import logging

logger = logging.getLogger(__name__)


class Authentication(object):
    def getUser(self, request):
        if "owrx-session" not in request.cookies:
            return None
        session_id = request.cookies["owrx-session"].value
        storage = SessionStorage.getSharedInstance()
        session = storage.getSession(session_id)
        if session is None:
            return None
        if "user" not in session:
            return None
        userList = UserList.getSharedInstance()
        user = None
        try:
            user = userList[session["user"]]
            storage.prolongSession(session_id)
        except KeyError:
            pass
        return user


class AuthorizationMixin(object):
    def __init__(self, handler, request, options):
        self.authentication = Authentication()
        self.user = self.authentication.getUser(request)
        super().__init__(handler, request, options)

    def isAuthorized(self):
        return self.user is not None and self.user.is_enabled() and not self.user.must_change_password

    def handle_request(self):
        if self.isAuthorized():
            super().handle_request()
        else:
            cookie = SimpleCookie()
            cookie["owrx-session"] = ""
            cookie["owrx-session"]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
            self.set_response_cookies(cookie)
            if (
                "x-requested-with" in self.request.headers
                and self.request.headers["x-requested-with"] == "XMLHttpRequest"
            ):
                self.send_response("{}", code=403)
            else:
                target = "{}login?{}".format(self.get_document_root(), parse.urlencode({"ref": self.request.path[1:]}))
                self.send_redirect(target)


class AdminAuthorizationMixin(AuthorizationMixin):
    """
    Like AuthorizationMixin, but also requires the user to be an administrator.
    Use it for the settings pages: bookmarks and the personal password change
    must stay available to any logged in user.
    """

    def isAuthorized(self):
        return super().isAuthorized() and self.user.is_admin()

    def handle_request(self):
        if not self.isAuthorized() and super().isAuthorized():
            # properly logged in but without privileges: bouncing them to the
            # login page would loop, since they would authenticate again and come
            # straight back here. Better to tell them.
            if (
                "x-requested-with" in self.request.headers
                and self.request.headers["x-requested-with"] == "XMLHttpRequest"
            ):
                self.send_response("{}", code=403)
            else:
                self.send_response(
                    "<!DOCTYPE HTML><html><head><title>Access denied</title>"
                    '<meta charset="utf-8"></head><body style="font-family:sans-serif;padding:2em;">'
                    "<h1>Access denied</h1>"
                    "<p>Your account does not have the administrator privileges "
                    "required for the settings.</p>"
                    '<p><a href="{root}">Back to the receiver</a></p>'
                    "</body></html>".format(root=self.get_document_root() or "./"),
                    code=403,
                    content_type="text/html",
                )
            return
        super().handle_request()
