"""Every server method the front end calls is actually whitelisted.

This exists because of one lost line. A `@frappe.whitelist()` sitting above
`reserve_batches` was swallowed when a helper was inserted directly above it, and
nothing said so: the code imported fine, every other test passed, and reserving a
batch in Material Mapping simply started answering

    Method Not Allowed — ... reserve_batches is not whitelisted

for anybody who pressed the button. It reached the live site that way. The decorator
is not referenced by any Python that runs, so no import error, no failing assertion
and no amount of reading the diff would have caught it -- only clicking the button.

So the check is mechanical: collect every `manufyxinvenzaerp.…` dotted path the
front end asks for -- client scripts, bundled JS, the scripts installed by setup.py --
and confirm each one resolves to a function this app has actually whitelisted.

It runs in CI as a unittest, on purpose. A guard against a decorator quietly going
missing is worth nothing if it has to be run by hand.
"""

import ast
import os
import re
import unittest

import frappe

APP = "manufyxinvenzaerp"
DOTTED = re.compile(r'["\'](manufyxinvenzaerp\.[A-Za-z0-9_.]+)["\']')
FRONT_END = (".js", ".json", ".html")


def _app_root():
    return frappe.get_app_path(APP)


def _whitelisted_methods():
    """Every dotted path this app exposes with @frappe.whitelist()."""
    found = set()
    for dirpath, _dirnames, filenames in os.walk(_app_root()):
        if "__pycache__" in dirpath or "/.git" in dirpath:
            continue
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            try:
                tree = ast.parse(open(path).read())
            except SyntaxError:
                continue
            rel = os.path.relpath(path, os.path.dirname(_app_root()))
            module = rel[:-3].replace(os.sep, ".")
            for node in ast.walk(tree):
                functions = []
                if isinstance(node, ast.FunctionDef):
                    functions = [node]
                elif isinstance(node, ast.ClassDef):
                    functions = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                for fn in functions:
                    for dec in fn.decorator_list:
                        if "whitelist" in ast.unparse(dec):
                            found.add("%s.%s" % (module, fn.name))
    return found


def _front_end_calls():
    """Every dotted path the browser asks the server for, and where it is asked."""
    asked = {}
    for dirpath, _dirnames, filenames in os.walk(_app_root()):
        if "__pycache__" in dirpath or "/.git" in dirpath:
            continue
        for filename in filenames:
            # setup.py is included: it carries the Client Scripts as strings.
            if not (filename.endswith(FRONT_END) or filename == "setup.py"):
                continue
            path = os.path.join(dirpath, filename)
            try:
                text = open(path, errors="ignore").read()
            except OSError:
                continue
            for match in DOTTED.finditer(text):
                dotted = match.group(1)
                # A trailing capital is a class (override targets), not a method.
                if dotted.rsplit(".", 1)[-1][:1].isupper():
                    continue
                asked.setdefault(dotted, set()).add(os.path.relpath(path, _app_root()))
    return asked


class TestWhitelistCoverage(unittest.TestCase):
    def test_every_front_end_call_is_whitelisted(self):
        whitelisted = _whitelisted_methods()
        self.assertTrue(whitelisted, "no whitelisted methods found — the scan is broken")

        missing = []
        for dotted, sources in sorted(_front_end_calls().items()):
            if dotted in whitelisted:
                continue
            # A path this app does not define at all belongs to frappe or erpnext.
            module, _, name = dotted.rpartition(".")
            try:
                frappe.get_attr(dotted)
            except Exception:
                continue
            missing.append("%s\n        called from: %s" % (dotted, ", ".join(sorted(sources))))

        self.assertEqual(
            [], missing,
            "These are called from the front end but carry no @frappe.whitelist(), "
            "so pressing the button that calls them answers 'Method Not Allowed':\n    "
            + "\n    ".join(missing),
        )

    def test_the_reservation_buttons_specifically(self):
        """The four that broke, named, so a failure points straight at the screen."""
        from manufyxinvenzaerp.production_management.doctype.material_planning import (
            material_planning,
        )

        # frappe.whitelist() records the function object in frappe.whitelisted --
        # a list, not an attribute on the function -- so membership is the check.
        for name in ("reserve_batches", "unreserve_batches",
                     "reserve_exact_match_batches", "unreserve_exact_match_batches",
                     "reassign_batch"):
            fn = getattr(material_planning, name)
            self.assertTrue(
                fn in frappe.whitelisted,
                "material_planning.%s is not whitelisted — the button that calls it "
                "will answer 'Method Not Allowed'" % name,
            )

    def test_no_private_helper_is_exposed(self):
        """The other half of the same accident.

        The decorator that went missing from reserve_batches did not vanish -- it
        ended up on the helper inserted above it, `_require_write`, which is a
        permission guard nobody outside this module should be able to call. One
        misplaced line, two bugs, and neither of them visible in the diff.

        A leading underscore is this codebase's way of saying "internal", so
        whitelisting one is always a mistake.
        """
        exposed = []
        for fn in frappe.whitelisted:
            module = getattr(fn, "__module__", "") or ""
            if not module.startswith(APP + "."):
                continue
            if fn.__name__.startswith("_"):
                exposed.append("%s.%s" % (module, fn.__name__))

        self.assertEqual(
            [], sorted(exposed),
            "These are private helpers but are reachable over the API:\n    "
            + "\n    ".join(sorted(exposed)),
        )
