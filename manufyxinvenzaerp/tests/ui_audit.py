"""Browser audit of every screen this app customises, for the v15 -> v16 move.

v16 changed the desk underneath us -- buttons escape their labels (so an icon passed
as HTML prints as raw <svg> text), the icon sprite changed, the grid renders every
in_list_view column -- and none of that shows up in a Python test. This opens each
screen the way a user does and reports what looks broken:

  * raw markup shown as text (<svg, &nbsp;, &lt;b&gt; ...) anywhere on the page
  * buttons with no visible label and no icon, or a label of "undefined"/"null"
  * buttons cut off by a too-narrow grid column
  * icons whose <use href="#icon-x"> points at a symbol that does not exist
    (Frappe draws an empty box for those)
  * field / section / tab labels reading "undefined"
  * sections that show a heading but no visible field
  * JavaScript errors (console + uncaught) and server error popups on load

Screens covered: list view and the latest record of every doctype this app touches
(own doctypes, doctype_js / doctype_list_js in hooks.py, Client Scripts, Custom Field
files), each tab of the form clicked in turn; the app's workspaces; its reports.

It only LOOKS: no save, no submit, no custom button is clicked.

Run (the bench must be serving the site):
    ./env/bin/python apps/manufyxinvenzaerp/manufyxinvenzaerp/tests/ui_audit.py \\
        --url http://localhost:8004 --user manufyx@gmail.com --password '...' [--only "Material Issue Plan"]

Writes ui_audit_report.json and a screenshot per problem screen into --out
(default: sites/ui_audit/), and prints a summary. Exit code 1 when anything is found.
"""

import argparse
import ast
import glob
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../manufyxinvenzaerp/manufyxinvenzaerp

# Things that are not ours to fix, or not real problems.
IGNORED_CONSOLE = (
	"favicon", "Failed to load resource: the server responded with a status of 404",
	"[Violation]", "DevTools", "socket.io", "WebSocket", "net::ERR_ABORTED",
	"unsupported command-line flag",
)

# Runs inside the page: everything checked on the screen as it stands.
PAGE_CHECKS = r"""
() => {
	const issues = [];
	const visible = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
		&& getComputedStyle(el).visibility !== "hidden";
	const where = (el) => {
		const s = el.closest("[data-fieldname]");
		const d = el.closest(".modal");
		return (d ? "dialog " : "") + (s ? "field " + s.getAttribute("data-fieldname") : "");
	};
	// Only the page on screen: Frappe keeps every page it has opened in the DOM, hidden.
	const root = (window.frappe && frappe.container && frappe.container.page) || document.body;
	const scope = [root, ...document.querySelectorAll(".modal.show")];

	// 1. raw markup rendered as text
	const raw = /<\/?(svg|use|span|div|b|i|br|button|a)\b|&nbsp;|&lt;|&gt;|&amp;nbsp;/i;
	for (const sc of scope) {
		const walker = document.createTreeWalker(sc, NodeFilter.SHOW_TEXT);
		let n;
		while ((n = walker.nextNode())) {
			const t = n.textContent;
			if (!raw.test(t)) continue;
			const el = n.parentElement;
			if (!el || !visible(el) || el.closest("textarea, .ql-editor, pre, code, .CodeMirror, .ace_editor, script, style")) continue;
			issues.push({ kind: "raw-markup", text: t.trim().slice(0, 140), where: where(el) });
		}
	}

	// 2. buttons
	for (const sc of scope) {
		for (const b of sc.querySelectorAll("button, .btn, a.btn")) {
			if (!visible(b)) continue;
			const text = (b.innerText || "").trim();
			const hasIcon = !!b.querySelector("svg, img, i[class*='fa'], .icon");
			const named = b.getAttribute("title") || b.getAttribute("aria-label") || b.getAttribute("data-label");
			if (!text && !hasIcon && !named) issues.push({ kind: "empty-button", text: b.outerHTML.slice(0, 120), where: where(b) });
			if (/^(undefined|null|NaN)$/i.test(text)) issues.push({ kind: "bad-button-label", text, where: where(b) });
		}
	}

	// 2b. buttons cut off by the grid cell they sit in (a Button field in a narrow column)
	for (const b of root.querySelectorAll(".grid-body .data-row button, .grid-body .data-row .btn")) {
		if (!visible(b)) continue;
		const cell = b.closest(".grid-static-col, .col");
		if (!cell) continue;
		const br = b.getBoundingClientRect(), cr = cell.getBoundingClientRect();
		if (br.right > cr.right + 1 || b.scrollWidth > b.clientWidth + 1)
			issues.push({ kind: "clipped-button", text: (b.innerText || "").trim(), where: where(b) });
	}

	// 3. icons pointing at nothing
	const missing = new Set();
	for (const u of [root, ...document.querySelectorAll(".modal.show")].flatMap((r) => [...r.querySelectorAll("svg use")])) {
		const href = u.getAttribute("href") || u.getAttribute("xlink:href") || "";
		if (!href.startsWith("#")) continue;
		const owner = u.closest("svg");
		if (!owner || !visible(owner)) continue;
		if (!document.getElementById(href.slice(1))) missing.add(href);
	}
	for (const h of missing) issues.push({ kind: "missing-icon", text: h });

	// 4. labels
	for (const l of root.querySelectorAll(".control-label, .section-head, .form-tabs .nav-link, .grid-heading-row .static-area, th")) {
		if (visible(l) && /\b(undefined|null)\b/.test(l.innerText)) issues.push({ kind: "bad-label", text: l.innerText.trim(), where: where(l) });
	}

	// 5. a section heading with nothing under it
	for (const s of root.querySelectorAll(".form-section")) {
		if (!visible(s)) continue;
		const head = s.querySelector(".section-head");
		if (!head || !visible(head) || !head.innerText.trim()) continue;
		if (head.classList.contains("collapsed") || s.classList.contains("collapsible") && !s.querySelector(".section-body:not(.hide)")) continue;
		const body = s.querySelector(".section-body");
		if (body && !visible(body)) continue;
		const fields = [...s.querySelectorAll(".frappe-control")].filter(visible);
		if (!fields.length) issues.push({ kind: "empty-section", text: head.innerText.trim() });
	}

	// 6. server error popups
	for (const m of document.querySelectorAll(".modal.show .msgprint, .modal.show .modal-body")) {
		const d = m.closest(".modal");
		const title = (d.querySelector(".modal-title") || {}).innerText || "";
		if (/error|exception|traceback|not permitted|not found/i.test(title + " " + m.innerText.slice(0, 300)))
			issues.push({ kind: "error-dialog", text: (title + ": " + m.innerText).trim().slice(0, 300) });
	}
	return issues;
}
"""


def customised_doctypes():
	"""Every doctype this app ships, scripts or customises -- read off the source."""
	names = set()
	for path in glob.glob(os.path.join(APP, "*", "doctype", "*", "*.json")):
		if os.path.basename(path)[:-5] != os.path.basename(os.path.dirname(path)):
			continue
		d = json.load(open(path))
		if d.get("doctype") == "DocType" and not d.get("istable") and not d.get("issingle"):
			names.add(d["name"])
		if d.get("doctype") == "DocType" and d.get("issingle"):
			names.add(d["name"])
	for path in glob.glob(os.path.join(APP, "*", "custom", "*.json")):
		d = json.load(open(path))
		if d.get("doctype"):
			names.add(d["doctype"])
	hooks = ast.parse(open(os.path.join(APP, "hooks.py")).read())
	for node in hooks.body:
		if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in ("doctype_js", "doctype_list_js"):
			names.update(ast.literal_eval(node.value).keys())
	return names


def app_reports():
	out = []
	for path in glob.glob(os.path.join(APP, "*", "report", "*", "*.json")):
		d = json.load(open(path))
		if d.get("doctype") == "Report" and not d.get("disabled"):
			out.append(d["name"])
	return sorted(out)


def app_workspaces():
	out = []
	for path in glob.glob(os.path.join(APP, "*", "workspace", "*", "*.json")):
		d = json.load(open(path))
		out.append(d["name"])
	return sorted(out)


def slug(name):
	return name.lower().replace(" ", "-")


class Audit:
	def __init__(self, page, out_dir):
		self.page, self.out = page, out_dir
		self.results = []
		self.console = []
		page.on("console", self._on_console)
		page.on("pageerror", lambda e: self.console.append(
			"uncaught: %s | %s" % (e, " / ".join((getattr(e, "stack", "") or "").splitlines()[1:4]).strip())))
		page.on("response", self._on_response)

	def _on_response(self, resp):
		"""A failed server call, named by its method and the server's own message."""
		if resp.status < 400 or "/api/" not in resp.url:
			return
		message = ""
		try:
			body = resp.json()
			message = body.get("exception") or body.get("exc_type") or ""
			if not message and body.get("_server_messages"):
				message = json.loads(json.loads(body["_server_messages"])[0]).get("message", "")
		except Exception:
			pass
		self.console.append("HTTP %s %s -- %s" % (resp.status, resp.url.split("/api/")[-1][:120], str(message)[:200]))

	def _on_console(self, msg):
		if msg.type != "error":
			return
		text = msg.text
		if any(s in text for s in IGNORED_CONSOLE) or text.startswith(("Failed to load resource", "Traceback")):
			return
		self.console.append(text[:300])

	def api(self, method, **args):
		return self.page.evaluate(
			"""async ([m, a]) => { try { const r = await frappe.call({ method: m, args: a, error_handlers: {} });
			   return r && r.message; } catch (e) { return null; } }""", [method, args])

	def settle(self, extra=1.0):
		try:
			self.page.wait_for_load_state("networkidle", timeout=15000)
		except Exception:
			pass
		try:
			self.page.wait_for_function("() => window.frappe && frappe.dom && !frappe.dom.freeze_count", timeout=15000)
		except Exception:
			pass
		time.sleep(extra)

	def check(self, screen, url, action=None):
		self.console = []
		try:
			self.page.goto(url)
			self.settle(1.5)
			self._tab_issues = []
			if action:
				action()
			issues = self.page.evaluate(PAGE_CHECKS) + self._tab_issues
		except Exception as e:
			issues = [{"kind": "load-failed", "text": str(e)[:300]}]
		issues += [{"kind": "js-error", "text": c} for c in dict.fromkeys(self.console)]
		# The same thing reported once per screen, not once per element.
		seen, unique = set(), []
		for i in issues:
			key = (i["kind"], i.get("text"), i.get("where"))
			if key not in seen:
				seen.add(key)
				unique.append(i)
		shot = None
		if unique:
			shot = os.path.join(self.out, re.sub(r"[^\w.-]+", "_", screen)[:80] + ".png")
			try:
				self.page.screenshot(path=shot, full_page=True)
			except Exception:
				shot = None
		self.results.append({"screen": screen, "url": url, "issues": unique, "screenshot": shot})
		mark = "OK  " if not unique else "%-4d" % len(unique)
		print("  %s %s" % (mark, screen))
		for i in unique[:6]:
			print("        - %-15s %s %s" % (i["kind"], i.get("where") or "", i.get("text", "")[:110]))

	def form_tabs(self):
		"""Click through every tab so each one's fields render and get checked."""
		tabs = self.page.locator(".form-tabs .nav-link:visible")
		issues = []
		for idx in range(tabs.count()):
			try:
				tabs.nth(idx).click()
				time.sleep(0.6)
				issues += self.page.evaluate(PAGE_CHECKS)
			except Exception:
				pass
		self._tab_issues = issues

	def doctype(self, doctype):
		base = "/desk/" + slug(doctype)
		single = self.page.evaluate(
			"async (dt) => { try { await frappe.model.with_doctype(dt); return !!frappe.get_meta(dt).issingle; }"
			" catch (e) { return false; } }", doctype)
		if not single:
			self.check(doctype + " — list", self.page.url.split("/desk")[0] + base)
			names = self.api("frappe.client.get_list", doctype=doctype, fields=["name"],
			                 order_by="modified desc", limit_page_length=1) or []
			target = base + "/" + names[0]["name"] if names else base + "/new"
			label = doctype + " — form (" + (names[0]["name"] if names else "new") + ")"
		else:
			target, label = base, doctype + " — form"

		self.check(label, self.page.url.split("/desk")[0] + target, action=self.form_tabs)


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--url", default="http://localhost:8004")
	ap.add_argument("--user", help="login user (with --password)")
	ap.add_argument("--password")
	ap.add_argument("--sid-file", help="file holding an existing session id (e.g. Administrator's) instead of a password")
	ap.add_argument("--out", default=os.path.join(os.getcwd(), "sites", "ui_audit"))
	ap.add_argument("--only", help="comma-separated doctypes / reports / workspaces to audit")
	ap.add_argument("--headed", action="store_true")
	args = ap.parse_args()
	os.makedirs(args.out, exist_ok=True)
	only = {s.strip() for s in args.only.split(",")} if args.only else None

	with sync_playwright() as pw:
		browser = pw.chromium.launch(headless=not args.headed)
		context = browser.new_context(viewport={"width": 1440, "height": 900})
		if args.sid_file:
			sid = open(args.sid_file).read().strip()
			context.add_cookies([{"name": "sid", "value": sid, "url": args.url}])
		page = context.new_page()
		if not args.sid_file:
			if not (args.user and args.password):
				sys.exit("give --user and --password, or --sid-file")
			page.goto(args.url + "/login")
			status = page.evaluate(
				"""async ([u, p]) => (await fetch('/api/method/login', {method: 'POST',
				   headers: {'Content-Type': 'application/json'}, body: JSON.stringify({usr: u, pwd: p})})).status""",
				[args.user, args.password])
			if status != 200:
				sys.exit("login failed (%s)" % status)
		page.goto(args.url + "/desk")
		page.wait_for_function("() => window.frappe && frappe.boot && frappe.boot.user", timeout=30000)
		audit = Audit(page, args.out)

		print("=== Workspaces ===")
		for ws in app_workspaces():
			if not only or ws in only:
				audit.check("Workspace " + ws, args.url + "/desk/" + slug(ws))

		print("=== Doctypes ===")
		allowed = set(page.evaluate("() => frappe.boot.user.can_read || []"))
		for dt in sorted(customised_doctypes()):
			if only and dt not in only:
				continue
			if page.evaluate("async (dt) => { try { await frappe.model.with_doctype(dt); return !!frappe.get_meta(dt).istable; }"
			                 " catch (e) { return false; } }", dt):
				continue  # a child table: its grid is checked on the parent's form
			if dt not in allowed:
				print("  --   %s (no read permission, skipped)" % dt)
				continue
			audit.doctype(dt)

		print("=== Reports ===")
		for rep in app_reports():
			if not only or rep in only:
				audit.check("Report " + rep, args.url + "/desk/query-report/" + rep)

		browser.close()

	bad = [r for r in audit.results if r["issues"]]
	report = os.path.join(args.out, "ui_audit_report.json")
	json.dump(audit.results, open(report, "w"), indent=1)
	print()
	print("%d screens checked, %d with problems, %d problems in all. Report: %s" % (
		len(audit.results), len(bad), sum(len(r["issues"]) for r in bad), report))
	sys.exit(1 if bad else 0)


if __name__ == "__main__":
	main()
