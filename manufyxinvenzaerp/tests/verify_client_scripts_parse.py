"""Every Client Script this app ships must be valid JavaScript.

Written after a one-character escaping mistake took the Sales Order form down.

The scripts live as Python triple-quoted strings in setup.py and are installed into
Client Script records. That is two languages in one file, and the trap is that they
disagree about the backslash:

    in setup.py:   message: "<p style=\\"color:#22863a\\">"
    what Python
    hands the
    browser:       message: "<p style="color:#22863a">"     <-- broken

Python consumes the backslash, so the escape intended for JavaScript never arrives,
the string closes early, and the whole script fails to parse. Frappe does not check
this. The Client Script installs fine, and the FORM stops loading -- the error came
up as "SyntaxError: Unexpected identifier 'color'" inside India Compliance's setup,
nowhere near the app that caused it.

Two things are checked, and the difference between them is the whole point:

  1. the RUNTIME VALUE of each constant in setup.py -- what Python produces, not
     what the file looks like. Reading the file text instead is what let this
     through: a raw-text scan shows the backslash still there and reports fine.
  2. every Client Script actually INSTALLED on the site, which catches a script
     edited in the UI or shipped by an older version of setup.py.

Needs `node` on PATH (it is, on any bench -- esbuild runs on it).

Run: bench --site manufact execute manufyxinvenzaerp.tests.verify_client_scripts_parse.run
"""

import ast
import os
import shutil
import subprocess
import tempfile

import frappe

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print("  %-4s %-62s got=%r want=%r" % ("OK" if ok else "FAIL", label, got, want))


def _parse_error(js):
    """Run the source through node's parser. Returns '' when it is valid."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False)
    handle.write(js or "")
    handle.close()
    try:
        result = subprocess.run(["node", "--check", handle.name],
                                capture_output=True, text=True)
    finally:
        os.unlink(handle.name)
    if result.returncode == 0:
        return ""
    # node prints the offending line, a caret, then the SyntaxError. The message
    # is the useful part.
    for line in result.stderr.split("\n"):
        if "Error" in line:
            return line.strip()
    return result.stderr.strip()[:160] or "unknown parse error"


def run():
    if not shutil.which("node"):
        print("node is not on PATH -- skipped")
        return

    print("=== 1. Client scripts embedded in setup.py, at their RUNTIME value ===")
    setup_path = os.path.join(frappe.get_app_path("manufyxinvenzaerp"), "setup.py")
    source = open(setup_path).read()
    tree = ast.parse(source)

    found = 0
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        name = getattr(node.targets[0], "id", "")
        if not name.endswith("CLIENT_SCRIPT"):
            continue
        found += 1
        # eval, not a read of the file text: the bug this exists for is invisible
        # until Python has finished with the escapes.
        segment = ast.get_source_segment(source, node.value)
        try:
            js = eval(segment, {"__builtins__": {}}, {})
        except Exception as exc:
            check("%s evaluates" % name, str(exc), "")
            continue
        check("%s parses" % name, _parse_error(js), "")

    check("constants were actually found (the scan is not silently empty)",
          found > 0, True)

    print()
    print("=== 2. Client scripts installed on this site ===")
    installed = frappe.get_all("Client Script", fields=["name", "dt", "enabled", "script"])
    for row in installed:
        if not row.enabled:
            continue
        check("%s (%s)" % (row.name, row.dt), _parse_error(row.script), "")

    print("  %d enabled Client Script(s) checked" % sum(1 for r in installed if r.enabled))

    total, failed = len(checks), checks.count(False)
    print()
    if failed:
        print("%d of %d CHECKS FAILED" % (failed, total))
    else:
        print("ALL %d CHECKS PASSED" % total)
