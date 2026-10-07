"""Gate policy: capability rules keyed on *what code is running*.

A policy is a plain document the governance root signs (``attest.GovernanceRoot.policy``)::

    {
      "default": "deny",
      "observer_freshness_s": 60,
      "rules": [
        {
          "id": "pay-small",
          "workload": "<measurement>" | "*",
          "action": "payments.transfer",
          "constraints": {"amount": {"max": 1000}, "currency": {"in": ["USD"]}},
          "requirement": {"mode": "observer", "observer": "obs-main", "max_risk": 0.3},
          "provenance": {"registry": "wm-registry", "status": "exact", "param": "body"},   # optional
          "rate_limit": {"max": 5, "window_s": 60}                                           # optional
        }
      ]
    }

``requirement.mode`` is ``auto`` (attestation alone suffices), ``observer``
(a fresh Layer 3 verdict under ``max_risk`` is required) or ``human`` (the
request is held for a signed approval; an observer threshold may still be
set and is checked first). ``requirement.observer`` names one observer or a
list of observers; with a list, *every* listed observer must supply a fresh
passing verdict (e.g. the safety repo's observer and NVIDIA Sentry).

A rule may also carry an ``egress`` block (``host``, ``port``, ``protocol``,
``access``) describing the network endpoint the action reaches; it is what
``oasp.to_openshell_network_policy`` translates into OpenShell policy.

Rules are capability grants: anything not matched by a rule is denied. A
rule bound to a specific measurement wins over a wildcard rule. In silicon
this table lives in protected SRAM loaded from a signed image, and "no
rule" is the absence of a path, not a software branch.
"""
from __future__ import annotations

import re
from typing import Any

MODES = ("auto", "observer", "human")


class PolicyError(ValueError):
    pass


def validate_policy(policy: Any) -> dict:
    if not isinstance(policy, dict):
        raise PolicyError("policy must be an object")
    if policy.get("default", "deny") != "deny":
        raise PolicyError("only default=deny policies are accepted")
    rules = policy.get("rules")
    if not isinstance(rules, list):
        raise PolicyError("policy.rules must be a list")
    seen: set[str] = set()
    for r in rules:
        for key in ("id", "workload", "action", "requirement"):
            if key not in r:
                raise PolicyError(f"rule missing {key}: {r}")
        if r["id"] in seen:
            raise PolicyError(f"duplicate rule id {r['id']}")
        seen.add(r["id"])
        mode = r["requirement"].get("mode")
        if mode not in MODES:
            raise PolicyError(f"rule {r['id']}: bad requirement mode {mode!r}")
        if mode in ("observer",) and ("observer" not in r["requirement"] or "max_risk" not in r["requirement"]):
            raise PolicyError(f"rule {r['id']}: observer requirement needs observer and max_risk")
        if "observer" in r["requirement"]:
            obs = r["requirement"]["observer"]
            if not (isinstance(obs, str) and obs) and not (isinstance(obs, list) and obs and all(isinstance(o, str) for o in obs)):
                raise PolicyError(f"rule {r['id']}: observer must be a name or a non-empty list of names")
        if "egress" in r and not all(k in r["egress"] for k in ("host",)):
            raise PolicyError(f"rule {r['id']}: egress needs a host")
        if "provenance" in r and r["provenance"].get("status") not in ("exact",):
            raise PolicyError(f"rule {r['id']}: provenance status must be 'exact'")
    policy.setdefault("observer_freshness_s", 60)
    policy.setdefault("hold_ttl_s", 3600)
    return policy


def find_rules(policy: dict, measurement: str, action: str) -> list[dict]:
    """Candidate rules for (measurement, action), most specific first. Empty list means deny."""
    exact = [r for r in policy["rules"] if r["action"] == action and r["workload"] == measurement]
    wild = [r for r in policy["rules"] if r["action"] == action and r["workload"] == "*"]
    return exact + wild


def find_rule(policy: dict, measurement: str, action: str) -> dict | None:
    rules = find_rules(policy, measurement, action)
    return rules[0] if rules else None


def select_rule(policy: dict, measurement: str, action: str, params: dict) -> tuple[dict | None, list[str]]:
    """First candidate whose constraints ``params`` satisfy; otherwise (None, violations of the first candidate).

    Several grants may exist for one action (a small-payment rule and a
    large-payment rule, say); the request takes whichever it fits.
    """
    candidates = find_rules(policy, measurement, action)
    if not candidates:
        return None, ["policy.no_rule"]
    first_violations: list[str] | None = None
    for rule in candidates:
        violations = check_constraints(rule.get("constraints", {}), params)
        if not violations:
            return rule, []
        if first_violations is None:
            first_violations = violations
    return None, first_violations or ["policy.no_rule"]


def check_constraints(constraints: dict[str, dict], params: dict) -> list[str]:
    """Return violations as reason codes ``constraint.<param>.<kind>``."""
    violations: list[str] = []
    for name, spec in (constraints or {}).items():
        if name not in params:
            if spec.get("required", True):
                violations.append(f"constraint.{name}.missing")
            continue
        value = params[name]
        if "type" in spec:
            want = {"number": (int, float), "string": (str,), "bool": (bool,)}[spec["type"]]
            if not isinstance(value, want) or (spec["type"] == "number" and isinstance(value, bool)):
                violations.append(f"constraint.{name}.type")
                continue
        if "max" in spec and not (isinstance(value, (int, float)) and not isinstance(value, bool) and value <= spec["max"]):
            violations.append(f"constraint.{name}.max")
        if "min" in spec and not (isinstance(value, (int, float)) and not isinstance(value, bool) and value >= spec["min"]):
            violations.append(f"constraint.{name}.min")
        if "in" in spec and value not in spec["in"]:
            violations.append(f"constraint.{name}.not_allowed")
        if "regex" in spec and not (isinstance(value, str) and re.fullmatch(spec["regex"], value)):
            violations.append(f"constraint.{name}.pattern")
        if "maxlen" in spec and not (isinstance(value, (str, list)) and len(value) <= spec["maxlen"]):
            violations.append(f"constraint.{name}.maxlen")
    return violations
