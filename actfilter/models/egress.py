"""Outbound-request allow-list with a request budget.

An agent may reach only (scheme, host, path-prefix, method) combinations the
policy lists, at most `max_requests` times per session. URLs are parsed
strictly and anything ambiguous is denied: credentials in the URL, a host given
as an IP address the policy does not name, non-default ports the policy does not
name, dot-segments or their percent-encodings in the path, whitespace or control
characters. The one repair offered is an upgrade from http to https when only
the https form is allowed.

Tool spec: {"model": "egress", "url_field": "url", "method_field": "method"}
Model params: {"allow": [{"host": "...", "path_prefix": "/", "methods": ["GET"],
                          "schemes": ["https"], "port": null}], "max_requests": 50}
"""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from ..core import Action, Reject, StateModel

_BAD = re.compile(r"[\x00-\x20\x7f\\]")
_DOTSEG = re.compile(r"(^|/)(\.|%2e){1,2}(/|$)", re.I)
DEFAULT_PORT = {"http": 80, "https": 443}


class EgressModel(StateModel):
    name = "egress"
    horizon = 1

    def __init__(self, allow: list, max_requests: int = 100):
        self.rules = []
        for r in allow:
            host = str(r["host"]).lower().rstrip(".")
            self.rules.append({"host": host, "path_prefix": r.get("path_prefix", "/"),
                               "methods": {m.upper() for m in r.get("methods", ["GET"])},
                               "schemes": set(r.get("schemes", ["https"])),
                               "port": r.get("port")})
        self.max_requests = int(max_requests)

    def initial_state(self):
        return {"requests": 0, "stopped": False, "off_list": False, "after_stop": False}

    def parse(self, tool, args, spec):
        url = args.get(spec.get("url_field", "url"))
        method = args.get(spec["method_field"], "GET") if spec.get("method_field") else "GET"
        if not isinstance(url, str) or not isinstance(method, str) or not url or _BAD.search(url):
            raise Reject("url must be a plain string without whitespace or control characters")
        try:
            u = urlsplit(url)
            port = u.port
        except ValueError as e:
            raise Reject(f"url does not parse: {e}")
        if u.scheme not in DEFAULT_PORT:
            raise Reject(f"scheme {u.scheme!r} is not http or https")
        if u.username is not None or u.password is not None or "@" in u.netloc:
            raise Reject("credentials in the url")
        host = (u.hostname or "").lower().rstrip(".")
        if not host:
            raise Reject("url has no host")
        path = u.path or "/"
        if _DOTSEG.search(path) or "%2f" in path.lower():
            raise Reject("dot-segments or encoded separators in the path")
        return Action("request", {"scheme": u.scheme, "host": host, "port": port,
                                  "path": path, "method": method.upper(),
                                  "query": u.query, "fragment": u.fragment})

    def render(self, action, args, spec):
        f = action.fields
        netloc = f["host"] + (f":{f['port']}" if f["port"] else "")
        args[spec.get("url_field", "url")] = urlunsplit((f["scheme"], netloc, f["path"],
                                                         f["query"], f["fragment"]))
        return args

    def _match(self, f) -> bool:
        for r in self.rules:
            if f["host"] != r["host"] or f["scheme"] not in r["schemes"]:
                continue
            port = f["port"] or DEFAULT_PORT[f["scheme"]]
            if port != (r["port"] or DEFAULT_PORT[f["scheme"]]):
                continue
            if not f["path"].startswith(r["path_prefix"]) or f["method"] not in r["methods"]:
                continue
            if _is_ip(f["host"]) and f["host"] != r["host"]:
                continue
            return True
        return False

    def predict(self, s, a):
        s = dict(s)
        if a.kind == "stop":
            s["stopped"] = True
            return s
        if s["stopped"]:
            s["after_stop"] = True
        s["requests"] += 1
        if not self._match(a.fields):
            s["off_list"] = True
        return s

    def violations(self, s):
        v = []
        if s["off_list"]:
            v.append("destination, path or method not on the allow-list")
        if s["requests"] > self.max_requests:
            v.append(f"request budget {self.max_requests} exceeded")
        if s["after_stop"]:
            v.append("request after the session was stopped")
        return v

    def terminal(self, s):
        return s["stopped"] or not s["off_list"]      # no request in flight: stopping is always possible

    def backup(self, s):
        return None if s["stopped"] else Action("stop", {})

    def candidates(self, s, a):
        f = a.fields
        if a.kind == "request" and f["scheme"] == "http" and f["port"] in (None, 80):
            return [Action("request", {**f, "scheme": "https", "port": None})]
        return []


def _is_ip(h: str) -> bool:
    try:
        ipaddress.ip_address(h.strip("[]"))
        return True
    except ValueError:
        return False
