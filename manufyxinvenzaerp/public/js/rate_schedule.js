// The Rate Schedule overwrite question, asked identically wherever it comes up.
//
// Lives in the app-wide bundle rather than beside either caller: BOM's script is
// loaded only on BOM and Production Plan's only on Production Plan (hooks.py
// doctype_js), so a helper defined in one is simply absent in the other.
// The bundle runs in esbuild's module scope, hence the explicit window.

// Shared by BOM and Production Plan Item: the question and the wording are the
// same in both, and the two must not drift into asking it differently.
//
// Declining restores the DRAWING's schedule rather than whatever was in the field
// a moment ago. "No, don't overwrite the drawing" and "make this document agree
// with the drawing" are the same instruction, and taking it literally means no
// per-field bookkeeping to get out of step.
window.mfx_confirm_rate_schedule_change = function (opts) {
	if (!opts.drawing) return;
	frappe.call({
		method: "manufyxinvenzaerp.drawing_management.rate_schedule_sync.get_rate_schedule_conflict",
		args: {
			drawing: opts.drawing,
			new_schedule: opts.new_schedule || "",
			source_doctype: opts.source_doctype,
			source_name: opts.source_name,
		},
		callback(r) {
			let d = r.message || {};
			if (!d.conflict) return;
			frappe.confirm(
				__("Drawing <b>{0}</b> already uses Rate Schedule <b>{1}</b>.", [
					frappe.utils.escape_html(d.drawing),
					frappe.utils.escape_html(d.current),
				]) +
				"<br><br>" +
				__("Changing it to <b>{0}</b> here changes it on the Drawing and on {1} other document(s) that follow it. Overwrite?", [
					frappe.utils.escape_html(opts.new_schedule || __("(none)")),
					d.target_count,
				]),
				() => {},                       // keep the new value; the save propagates it
				() => opts.on_decline(d.current)
			);
		},
	});
};
