from owrx.controllers.template import WebpageController
from owrx.controllers.admin import AdminAuthorizationMixin
from owrx.controllers.settings import SettingsBreadcrumb
from owrx.users import UserList, User, DefaultPasswordClass
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem, BreadcrumbMixin
from urllib.parse import parse_qs, urlencode
from html import escape

import logging

logger = logging.getLogger(__name__)


class UsersController(AdminAuthorizationMixin, BreadcrumbMixin, WebpageController):
    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("User management", "settings/users"))

    def template_variables(self):
        variables = super().template_variables()
        variables["users"] = self.render_table()
        variables["message"] = self.render_message()
        return variables

    def render_message(self):
        if "msg" not in self.request.query:
            return ""
        messages = {
            "added": ("success", "User created."),
            "deleted": ("success", "User deleted."),
            "enabled": ("success", "User enabled."),
            "disabled": ("success", "User disabled."),
            "password": ("success", "Password updated. The user will have to change it at the next login."),
            "promoted": ("success", "Administrator privileges granted."),
            "demoted": ("success", "Administrator privileges revoked."),
            "exists": ("danger", "A user with that name already exists."),
            "invalid": ("danger", "User name and password are required."),
            "self": ("danger", "You cannot act on the account you are logged in with. Use /pwchange for your own password."),
            "notfound": ("danger", "No such user."),
            "lastadmin": ("danger", "At least one administrator must remain."),
        }
        key = self.request.query["msg"][0]
        if key not in messages:
            return ""
        level, text = messages[key]
        return '<div class="alert alert-{0}">{1}</div>'.format(level, escape(text))

    def render_table(self):
        users = sorted(UserList.getSharedInstance().values(), key=lambda u: u.name.lower())
        return """
            <table class="table">
                <tr>
                    <th>User</th>
                    <th>Role</th>
                    <th>State</th>
                    <th>Password</th>
                    <th>Actions</th>
                </tr>
                {rows}
            </table>
        """.format(rows="".join(self.render_user(u) for u in users))

    def render_user(self, user: User):
        is_current = self.user is not None and self.user.name == user.name

        if user.is_enabled():
            state = '<span class="badge badge-success">enabled</span>'
            state_action, state_label, state_class = "disable", "Disable", "btn-warning"
        else:
            state = '<span class="badge badge-secondary">disabled</span>'
            state_action, state_label, state_class = "enable", "Enable", "btn-success"

        if user.is_admin():
            role = '<span class="badge badge-primary">administrator</span>'
            role_action, role_label = "demote", "Revoke admin"
        else:
            role = '<span class="badge badge-light">user</span>'
            role_action, role_label = "promote", "Make admin"

        if user.must_change_password:
            password = '<span class="badge badge-warning">must change</span>'
        else:
            password = '<span class="text-muted">set</span>'

        if is_current:
            # without this you can lock yourself out of the settings
            actions = '<span class="text-muted">this is the account you are logged in with</span>'
        else:
            actions = (
                self.render_action_button(user.name, state_action, state_label, state_class)
                + self.render_action_button(user.name, role_action, role_label, "btn-info")
                + self.render_action_button(user.name, "delete", "Delete", "btn-danger")
            )

        return """
            <tr>
                <td>{name}</td>
                <td>{role}</td>
                <td>{state}</td>
                <td>{password}</td>
                <td class="d-flex" style="gap: 6px;">{actions}</td>
            </tr>
        """.format(name=escape(user.name), role=role, state=state, password=password, actions=actions)

    def render_action_button(self, username, action, label, css_class):
        return """
            <form method="POST" action="users" class="d-inline">
                <input type="hidden" name="action" value="{action}">
                <input type="hidden" name="username" value="{username}">
                <button type="submit" class="btn btn-sm {css_class}">{label}</button>
            </form>
        """.format(action=action, username=escape(username, quote=True), css_class=css_class, label=label)

    def _count_admins(self, userlist):
        return sum(1 for u in userlist.values() if u.is_admin() and u.is_enabled())

    def _redirect(self, msg):
        self.send_redirect("{0}settings/users?{1}".format(self.get_document_root(), urlencode({"msg": msg})))

    def processFormData(self):
        data = parse_qs(self.get_body().decode("utf-8"))
        data = {k: v[0] for k, v in data.items()}
        action = data.get("action", "")

        if action == "add":
            return self.addUser(data)

        username = data.get("username", "")
        userlist = UserList.getSharedInstance()
        if username not in userlist:
            return self._redirect("notfound")
        if self.user is not None and self.user.name == username:
            return self._redirect("self")

        user = userlist[username]
        if action == "enable":
            user.enable()
            userlist.store()
            return self._redirect("enabled")
        if action == "disable":
            if user.is_admin() and self._count_admins(userlist) <= 1:
                return self._redirect("lastadmin")
            user.disable()
            userlist.store()
            return self._redirect("disabled")
        if action == "promote":
            user.admin = True
            userlist.store()
            return self._redirect("promoted")
        if action == "demote":
            if self._count_admins(userlist) <= 1:
                return self._redirect("lastadmin")
            user.admin = False
            userlist.store()
            return self._redirect("demoted")
        if action == "delete":
            if user.is_admin() and self._count_admins(userlist) <= 1:
                return self._redirect("lastadmin")
            userlist.deleteUser(user)
            return self._redirect("deleted")
        if action == "password":
            password = data.get("password", "")
            if not password:
                return self._redirect("invalid")
            user.setPassword(DefaultPasswordClass(password), must_change_password=True)
            userlist.store()
            return self._redirect("password")

        self._redirect("invalid")

    def addUser(self, data):
        username = data.get("username", "").strip()
        password = data.get("password", "")
        if not username or not password:
            return self._redirect("invalid")

        userlist = UserList.getSharedInstance()
        if username in userlist:
            return self._redirect("exists")

        # addUser already writes to disk
        userlist.addUser(
            User(
                name=username,
                enabled=True,
                password=DefaultPasswordClass(password),
                must_change_password=data.get("must_change_password", "") == "on",
                # new users start without privileges: access to the settings has
                # to be granted deliberately
                admin=data.get("admin", "") == "on",
            )
        )
        logger.info("user created from settings page: %s", username)
        self._redirect("added")

    def indexAction(self):
        self.serve_template("settings/users.html", **self.template_variables())
