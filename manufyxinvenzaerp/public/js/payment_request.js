function refresh_fund_usage(frm) {
	if (!frm.doc.custom_source_of_funds) {
		frm.set_value("custom_already_used_amount", 0);
		frm.set_value("custom_balance_amount", 0);
		return;
	}
	frappe.call({
		method: "manufyxinvenzaerp.accounts_management.payment_request.get_fund_usage",
		args: {
			payment_entry: frm.doc.custom_source_of_funds,
			payment_request: frm.doc.name,
		},
		callback(r) {
			if (!r.message) return;
			frm.set_value("custom_already_used_amount", r.message.already_used_amount);
			frm.set_value("custom_balance_amount", r.message.balance_amount);
		},
	});
}

frappe.ui.form.on("Payment Request", {
	setup(frm) {
		frm.set_query("custom_source_of_funds", function() {
			return {
				query: "manufyxinvenzaerp.accounts_management.payment_request.payment_entry_query",
			};
		});
	},

	refresh(frm) {
		refresh_fund_usage(frm);

		// Core ERPNext only offers "Create Payment Entry" for Outward requests (Inward
		// is meant to go through the payment-gateway email/phone link). That's by
		// design, not a bug -- but create_payment_entry() server-side is fully generic,
		// so expose the same action here for Inward/advance requests too.
		if (
			frm.doc.payment_request_type == "Inward" &&
			frm.doc.docstatus == 1 &&
			["Requested", "Partially Paid"].includes(frm.doc.status)
		) {
			frm.add_custom_button(__("Create Payment Entry"), function () {
				frappe.call({
					method: "erpnext.accounts.doctype.payment_request.payment_request.make_payment_entry",
					args: { docname: frm.doc.name },
					freeze: true,
					callback: function (r) {
						if (!r.exc) {
							frappe.model.sync(r.message);
							frappe.set_route("Form", r.message.doctype, r.message.name);
						}
					},
				});
			}).addClass("btn-primary");
		}
	},

	custom_source_of_funds(frm) {
		refresh_fund_usage(frm);
	},
});
