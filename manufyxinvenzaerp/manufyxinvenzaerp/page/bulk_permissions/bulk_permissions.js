// Update Permissions for New Doctypes and Reports
//
// Pick a role, tick what it should be able to do, and apply it across every
// doctype and report this app owns in one pass -- instead of opening each one in
// the Role Permissions Manager and ticking the same boxes a dozen times.
//
// The list is derived from the app's own modules, so a doctype added later is
// covered without anyone remembering to add it here.

frappe.pages["bulk-permissions"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Update Permissions for New Doctypes and Reports"),
		single_column: true,
	});

	new BulkPermissions(page);
};

const PERM_TYPES = [
	{ field: "read", label: __("Read") },
	{ field: "write", label: __("Write") },
	{ field: "create", label: __("Create") },
	{ field: "delete", label: __("Delete") },
	{ field: "submit", label: __("Submit") },
	{ field: "cancel", label: __("Cancel") },
	{ field: "amend", label: __("Amend") },
	{ field: "print", label: __("Print") },
	{ field: "email", label: __("Email") },
	{ field: "export", label: __("Export") },
	{ field: "import", label: __("Import") },
	{ field: "report", label: __("Report") },
	{ field: "share", label: __("Share") },
];

// What "all permission" means when the user just wants the role to work.
const COMMON_SET = ["read", "write", "create", "delete", "print", "email",
	"export", "import", "report", "share", "submit", "cancel", "amend"];

class BulkPermissions {
	constructor(page) {
		this.page = page;
		this.targets = null;
		this.$body = $('<div class="bp-body" style="padding:4px 0 20px">').appendTo(page.main);
		this.render_shell();
		this.load_targets();
	}

	render_shell() {
		this.$body.html(`
			<div class="bp-intro text-muted" style="font-size:12px;margin-bottom:14px">
				${__("Choose a role and tick what it should be able to do. The permissions are applied to every doctype and report this app owns, in one pass.")}
				<br>${__("Existing permissions are never removed unless you ask for it, and running this twice changes nothing the second time.")}
			</div>
			<div class="row">
				<div class="col-sm-5"><div class="bp-role"></div></div>
				<div class="col-sm-7"><div class="bp-summary"></div></div>
			</div>
			<div class="bp-perms" style="margin:14px 0"></div>
			<div class="bp-targets"></div>
			<div class="bp-actions" style="margin-top:16px"></div>
			<div class="bp-result" style="margin-top:16px"></div>
		`);

		this.role_control = frappe.ui.form.make_control({
			parent: this.$body.find(".bp-role"),
			df: {
				fieldtype: "Link",
				options: "Role",
				label: __("Role"),
				fieldname: "bp_role",
				reqd: 1,
				get_query: () => ({ filters: { disabled: 0, is_custom: ["in", [0, 1]] } }),
				onchange: () => this.load_role_state(),
			},
			render_input: true,
		});
	}

	load_targets() {
		frappe.call({
			method: "manufyxinvenzaerp.permissions_bulk.get_targets",
			freeze: true,
			freeze_message: __("Reading this app's doctypes and reports…"),
			callback: (r) => {
				if (!r.message) return;
				this.targets = r.message;
				this.render_perms();
				this.render_targets();
				this.render_actions();
			},
		});
	}

	render_perms() {
		const $wrap = this.$body.find(".bp-perms").empty();
		$wrap.append(`<div style="font-weight:600;margin-bottom:6px">${__("Permissions to grant")}</div>`);
		const $row = $('<div style="display:flex;flex-wrap:wrap;gap:14px 22px">').appendTo($wrap);
		PERM_TYPES.forEach((p) => {
			$(`<label style="font-weight:normal;margin:0;cursor:pointer">
				<input type="checkbox" class="bp-perm" data-field="${p.field}"> ${p.label}
			</label>`).appendTo($row);
		});
		const $links = $('<div style="margin-top:8px;font-size:12px">').appendTo($wrap);
		$(`<a href="#" style="margin-right:14px">${__("Select all")}</a>`)
			.appendTo($links)
			.on("click", (e) => {
				e.preventDefault();
				$wrap.find(".bp-perm").prop("checked", true);
			});
		$(`<a href="#" style="margin-right:14px">${__("Everything a working role needs")}</a>`)
			.appendTo($links)
			.on("click", (e) => {
				e.preventDefault();
				$wrap.find(".bp-perm").each(function () {
					$(this).prop("checked", COMMON_SET.indexOf($(this).data("field")) !== -1);
				});
			});
		$(`<a href="#">${__("Clear")}</a>`)
			.appendTo($links)
			.on("click", (e) => {
				e.preventDefault();
				$wrap.find(".bp-perm").prop("checked", false);
			});

		$(`<div class="text-muted" style="font-size:11px;margin-top:6px">
			${__("Submit, Cancel and Amend are written only where the doctype is submittable — elsewhere they mean nothing and are skipped.")}
		</div>`).appendTo($wrap);
	}

	render_targets() {
		const $wrap = this.$body.find(".bp-targets").empty();
		const dts = this.targets.doctypes || [];
		const reports = this.targets.reports || [];

		$wrap.append(`<div style="font-weight:600;margin-bottom:6px">
			${__("What will be updated")}
			<span class="text-muted" style="font-weight:normal">
				— ${__("{0} doctype(s), {1} report(s)", [dts.length, reports.length])}
			</span>
		</div>`);
		$wrap.append(`<div class="text-muted" style="font-size:11px;margin-bottom:8px">
			${__("Untick anything this role should not reach. Modules covered: {0}.",
				[(this.targets.modules || []).join(", ")])}
		</div>`);

		const $grid = $('<div class="row">').appendTo($wrap);
		const $left = $('<div class="col-sm-6">').appendTo($grid);
		const $right = $('<div class="col-sm-6">').appendTo($grid);

		const cell = (kind, name, extra) =>
			`<label style="display:block;font-weight:normal;margin:0 0 3px;cursor:pointer">
				<input type="checkbox" class="bp-target" data-kind="${kind}"
					data-name="${frappe.utils.escape_html(name)}" checked>
				${frappe.utils.escape_html(name)}
				${extra ? `<span class="text-muted" style="font-size:11px"> · ${extra}</span>` : ""}
			</label>`;

		$left.append(`<div style="font-size:12px;font-weight:600;margin-bottom:4px">${__("Doctypes")}</div>`);
		dts.forEach((d) => {
			const bits = [];
			if (d.issingle) bits.push(__("single"));
			if (d.is_submittable) bits.push(__("submittable"));
			$left.append(cell("doctype", d.name, bits.join(", ")));
		});

		$right.append(`<div style="font-size:12px;font-weight:600;margin-bottom:4px">${__("Reports")}</div>`);
		reports.forEach((r) => {
			$right.append(cell("report", r.name, r.ref_doctype));
		});
		$right.append(`<div class="text-muted" style="font-size:11px;margin-top:8px">
			${__("A report needs its own role list AND read access on its reference doctype. Both are handled — which is why granting permissions through the Role Permissions Manager alone leaves reports invisible.")}
		</div>`);
	}

	render_actions() {
		const $wrap = this.$body.find(".bp-actions").empty();
		$('<label style="font-weight:normal;display:block;margin-bottom:10px;cursor:pointer">')
			.append(`<input type="checkbox" class="bp-remove-others">
				${__("Also switch OFF anything not ticked, so the role ends up with exactly this")}`)
			.appendTo($wrap);

		this.page.set_primary_action(__("Update Permissions"), () => this.apply());
		$(`<button class="btn btn-default btn-sm">${__("Show what this role can do now")}</button>`)
			.appendTo($wrap)
			.on("click", () => this.load_role_state(true));
	}

	selected(kind) {
		return this.$body
			.find(`.bp-target[data-kind="${kind}"]:checked`)
			.map(function () { return $(this).data("name"); })
			.get();
	}

	load_role_state(announce) {
		const role = this.role_control.get_value();
		const $sum = this.$body.find(".bp-summary").empty();
		if (!role) return;
		frappe.call({
			method: "manufyxinvenzaerp.permissions_bulk.get_role_state",
			args: { role: role },
			freeze: !!announce,
			callback: (r) => {
				if (!r.message) return;
				const dts = r.message.doctypes || {};
				const reports = r.message.reports || {};
				const readable = Object.keys(dts).filter((d) => dts[d].read).length;
				const writable = Object.keys(dts).filter((d) => dts[d].write).length;
				const visible = Object.keys(reports).filter((n) => reports[n].granted).length;
				$sum.html(`<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 10px;font-size:12px">
					<b>${frappe.utils.escape_html(role)}</b> ${__("can currently")}:
					${__("read {0} of {1} doctypes", [readable, Object.keys(dts).length])} ·
					${__("write {0}", [writable])} ·
					${__("open {0} of {1} reports", [visible, Object.keys(reports).length])}
				</div>`);
			},
		});
	}

	apply() {
		const role = this.role_control.get_value();
		const permissions = this.$body
			.find(".bp-perm:checked")
			.map(function () { return $(this).data("field"); })
			.get();
		const doctypes = this.selected("doctype");
		const reports = this.selected("report");
		const remove_others = this.$body.find(".bp-remove-others").is(":checked") ? 1 : 0;

		if (!role) {
			frappe.msgprint(__("Choose a role first."));
			return;
		}
		if (!permissions.length) {
			frappe.msgprint(__("Tick at least one permission."));
			return;
		}

		// Permissions are worth one deliberate confirmation, with the numbers on
		// screen rather than in the button label.
		frappe.confirm(
			__("Give <b>{0}</b> these permissions — {1} — on {2} doctype(s) and access to {3} report(s)?",
				[frappe.utils.escape_html(role), permissions.join(", "),
					doctypes.length, reports.length]) +
			(remove_others
				? "<br><br><b style='color:#b91c1c'>" +
					__("Anything not ticked will be switched off for this role.") + "</b>"
				: ""),
			() => {
				frappe.call({
					method: "manufyxinvenzaerp.permissions_bulk.apply_permissions",
					args: {
						role: role,
						permissions: JSON.stringify(permissions),
						doctypes: JSON.stringify(doctypes),
						reports: JSON.stringify(reports),
						remove_others: remove_others,
					},
					freeze: true,
					freeze_message: __("Updating permissions…"),
					callback: (r) => {
						if (!r.message) return;
						this.render_result(r.message);
						this.load_role_state();
						frappe.show_alert({
							message: __("{0} doctype(s) and {1} report(s) updated for {2}. Ask them to reload.",
								[r.message.doctype_count, r.message.report_count, role]),
							indicator: "green",
						}, 8);
					},
				});
			}
		);
	}

	render_result(res) {
		const $wrap = this.$body.find(".bp-result").empty();
		const rows = (res.changed || []).map((c) =>
			`<tr><td style="padding:3px 10px 3px 0">${c.type}</td>
			 <td style="padding:3px 10px 3px 0">${frappe.utils.escape_html(c.name)}</td>
			 <td style="padding:3px 0;color:#15803d">${(c.applied || []).join(", ")}</td></tr>`
		).join("");
		const skipped = (res.skipped || []).map((s) =>
			`<li>${frappe.utils.escape_html(s.name)} — ${s.reason}</li>`).join("");

		$wrap.html(`
			<div style="border:1px solid #e2e8f0;border-radius:6px;padding:12px">
				<div style="font-weight:600;margin-bottom:8px">
					${__("Updated {0} doctype(s) and {1} report(s) for {2}",
						[res.doctype_count, res.report_count, frappe.utils.escape_html(res.role)])}
				</div>
				<div style="max-height:260px;overflow:auto">
					<table style="font-size:12px;width:100%">${rows}</table>
				</div>
				${skipped ? `<div style="margin-top:10px;font-size:12px">
					<b>${__("Left alone")}</b><ul style="margin:4px 0 0 18px">${skipped}</ul></div>` : ""}
				<div class="text-muted" style="font-size:11px;margin-top:10px">
					${__("Users holding this role need to reload their browser before the change takes effect for them.")}
				</div>
			</div>
		`);
	}
}
