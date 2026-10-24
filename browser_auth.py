"""Optional HTTPS browser authentication for X-ONU-SFPP Dashboard."""

import hmac
import ipaddress
import os
import threading
import time
from urllib.parse import urlsplit

from flask import jsonify, redirect, render_template, request, url_for

from browser_sessions import (
    BrowserSessions, COOKIE_NAME, REMEMBER_DAYS_OPTIONS
)


class BrowserAuth:
    def __init__(self, db_path, public_origin, username, password):
        parsed = urlsplit(public_origin)

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError(
                "DASHBOARD_PUBLIC_ORIGIN must be an HTTPS origin "
                "without a path, query, or credentials"
            )

        try:
            parsed.port
        except ValueError as exc:
            raise RuntimeError(
                "Invalid DASHBOARD_PUBLIC_ORIGIN port"
            ) from exc

        self.origin = "https://" + parsed.netloc.lower()
        self.host = parsed.netloc.lower()
        self.username = username
        self.password = password

        self.sessions = BrowserSessions(db_path)
        self.sessions.initialize()

        self._fail_lock = threading.Lock()
        self._failures = {}
        self.trusted_proxy_ips = self._load_trusted_proxy_ips()

    def _same_origin(self):
        return (
            request.host.lower() == self.host
            and request.headers.get("Origin") == self.origin
            and request.headers.get(
                "Sec-Fetch-Site", "same-origin"
            ) in ("same-origin", "none")
        )

    @staticmethod
    def _load_trusted_proxy_ips():
        raw = os.environ.get(
            "DASHBOARD_TRUSTED_PROXY_IPS", ""
        ).strip()

        if not raw:
            return frozenset()

        if len(raw) > 1024:
            raise RuntimeError(
                "Trusted proxy IP configuration is too long"
            )

        try:
            return frozenset(
                ipaddress.ip_address(value.strip())
                for value in raw.split(",")
            )
        except ValueError as exc:
            raise RuntimeError(
                "DASHBOARD_TRUSTED_PROXY_IPS must contain "
                "comma-separated IP addresses"
            ) from exc

    def _login_client_key(self):
        peer = request.remote_addr or "unknown"

        try:
            peer_address = ipaddress.ip_address(peer)
        except ValueError:
            return peer

        if peer_address not in self.trusted_proxy_ips:
            return peer

        forwarded = request.headers.get(
            "X-Forwarded-For", ""
        )

        # Trust only a single, valid address from the
        # explicitly trusted reverse proxy. Fall back to
        # its connection IP for ambiguous header chains.
        parts = forwarded.split(",")

        if len(parts) != 1:
            return peer

        try:
            client = ipaddress.ip_address(parts[0].strip())
        except ValueError:
            return peer

        return client.compressed

    def _login_allowed(self, key):
        now = time.monotonic()

        with self._fail_lock:
            if len(self._failures) > 1024:
                self._failures = {
                    address: attempts
                    for address, attempts in self._failures.items()
                    if attempts and now - attempts[-1] < 300
                }

            recent = [
                ts for ts in self._failures.get(key, [])
                if now - ts < 300
            ]

            self._failures[key] = recent

            return len(recent) < 5

    def _record_failure(self, key):
        with self._fail_lock:
            self._failures.setdefault(
                key, []
            ).append(time.monotonic())

    def check_request(self):
        if request.path == "/api/health":
            return None

        if request.path.startswith("/static/"):
            return None

        if request.host.lower() != self.host:
            return jsonify(error="Invalid host"), 400

        if request.path in (
            "/login",
            "/api/browser-login",
        ):
            return None

        token = request.cookies.get(COOKIE_NAME)
        record = self.sessions.find(token)

        if record is None:
            if request.path.startswith("/api/"):
                return jsonify(
                    error="Authentication required"
                ), 401

            destination = request.path

            return redirect(
                url_for(
                    "browser_login_page",
                    next=destination,
                )
            )

        if request.method not in (
            "GET", "HEAD", "OPTIONS"
        ):
            if not self._same_origin():
                return jsonify(
                    error="Invalid request origin"
                ), 403

            if not self.sessions.verify_csrf(
                token,
                request.headers.get("X-CSRF-Token"),
            ):
                return jsonify(
                    error="Invalid CSRF token"
                ), 403

        return None

    def install(self, app):
        @app.get("/trusted-browsers")
        def trusted_browsers_page():
            return render_template(
                "trusted_browsers.html",
                active_page="sessions",
            )

        @app.get("/login")
        def browser_login_page():
            return render_template("login.html")

        @app.post("/api/browser-login")
        def browser_login():
            if not self._same_origin():
                return jsonify(
                    error="Invalid request origin"
                ), 403

            data = request.get_json(silent=True)

            if not isinstance(data, dict):
                return jsonify(error="Invalid request"), 400

            username = data.get("username")
            password = data.get("password")
            remember = data.get("remember", False)
            remember_days = data.get("remember_days", 7)

            if (
                not isinstance(username, str)
                or not isinstance(password, str)
                or not isinstance(remember, bool)
                or type(remember_days) is not int
                or remember_days not in REMEMBER_DAYS_OPTIONS
                or len(username) > 1024
                or len(password) > 1024
            ):
                return jsonify(error="Invalid request"), 400

            peer = self._login_client_key()

            if not self._login_allowed(peer):
                return jsonify(
                    error="Too many login attempts"
                ), 429

            user_ok = hmac.compare_digest(
                username, self.username
            )
            pass_ok = hmac.compare_digest(
                password, self.password
            )

            if not (user_ok & pass_ok):
                self._record_failure(peer)

                return jsonify(
                    error="Invalid username or password"
                ), 401

            token, expires_at = self.sessions.issue(
                remember=remember,
                browser_label=request.user_agent.string,
                remember_days=remember_days,
            )

            response = jsonify(
                ok=True,
                expires_at=expires_at,
            )

            response.set_cookie(
                COOKIE_NAME,
                token,
                secure=True,
                httponly=True,
                samesite="Lax",
                path="/",
                max_age=(
                    remember_days * 24 * 60 * 60
                    if remember else None
                ),
            )

            return response

        @app.get("/api/browser-session")
        def browser_session():
            token = request.cookies.get(COOKIE_NAME)
            record = self.sessions.find(token)

            return jsonify(
                id=record["id"],
                expires_at=record["expires_at"],
                remembered=record["remembered"],
                csrf_token=self.sessions.csrf_token(token),
            )

        @app.post("/api/browser-logout")
        def browser_logout():
            self.sessions.revoke(
                request.cookies.get(COOKIE_NAME)
            )

            response = jsonify(ok=True)

            response.delete_cookie(
                COOKIE_NAME,
                path="/",
                secure=True,
                httponly=True,
                samesite="Lax",
            )

            return response

        @app.get("/api/browser-sessions")
        def browser_sessions():
            return jsonify(self.sessions.active())

        @app.delete("/api/browser-sessions/<session_id>")
        def browser_revoke_session(session_id):
            current_token = request.cookies.get(COOKIE_NAME)
            current_record = self.sessions.find(current_token)
            revoking_current = (
                current_record is not None
                and hmac.compare_digest(
                    current_record["id"], session_id
                )
            )

            revoked = self.sessions.revoke_id(session_id)
            response = jsonify(revoked=revoked)

            if revoked and revoking_current:
                response.delete_cookie(
                    COOKIE_NAME,
                    path="/",
                    secure=True,
                    httponly=True,
                    samesite="Lax",
                )

            return response

        @app.after_request
        def browser_auth_cache_headers(response):
            if not request.path.startswith("/static/"):
                response.headers["Cache-Control"] = "no-store"

            return response
