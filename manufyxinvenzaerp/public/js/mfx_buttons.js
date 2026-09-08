// App-wide button colouring.
//
// Frappe paints every custom button the same grey (btn-default / btn-secondary),
// so on a form carrying eight of them nothing says which one is the next step and
// which one undoes a decision already made. Material Planning solved that for
// itself with a local _MFX_BTN_CSS; this file is that same system promoted to the
// whole app so one rule governs every custom doctype.
//
// Four tones, and the meaning is the point -- pick by what the button DOES, not by
// what looks good next to its neighbour:
//
//   primary  (blue)          the next step in the flow   Check Stock, Reserve, Transfer
//   info     (outlined blue) look, do not change         Check Mapping, Validate Stock
//   alt      (orange)        undo / re-do / overwrite    Unreserve, Update Batch, Reassign
//   danger   (red)           destructive, writes off     Process Loss
//   (none)   (grey)          navigation and housekeeping View All, Download, Open MIP
//
// `info` exists because "check this and tell me" is a real third thing, and the
// buttons doing it were invisible in grey while being wrong in blue: Check Mapping
// and Validate Stock read the plan and report, they write nothing. Outlined rather
// than filled so they stay clearly secondary to whatever the actual next step is.
//
// Grey is deliberate, not "unstyled": if every button is coloured, colour stops
// carrying information. Leave navigation alone.
//
// Loaded through manufyxinvenzaerp.bundle.js, which runs in esbuild's module
// scope -- so everything callers need is attached to `window` at the bottom of
// this file, exactly as manual_renderer.js does.

const MFX_BTN_STYLE_ID = "mfx-action-btn-style";

// !important throughout: Frappe's own .btn-default/.btn-secondary rules are more
// specific than a bare class, so without it the grey wins and nothing changes.
const MFX_BTN_CSS = `
.mfx-action-btn, .mfx-action-btn:focus {
	background-color: var(--blue-500) !important;
	border-color: var(--blue-500) !important;
	color: var(--white, #fff) !important;
}
.mfx-action-btn:hover { filter: brightness(0.92); }
.mfx-action-btn-alt, .mfx-action-btn-alt:focus {
	background-color: var(--orange-500) !important;
	border-color: var(--orange-500) !important;
	color: var(--white, #fff) !important;
}
.mfx-action-btn-alt:hover { filter: brightness(0.92); }
.mfx-action-btn-danger, .mfx-action-btn-danger:focus {
	background-color: var(--red-500) !important;
	border-color: var(--red-500) !important;
	color: var(--white, #fff) !important;
}
.mfx-action-btn-danger:hover { filter: brightness(0.92); }
/* Outlined, and transparent rather than tinted: a fixed pale fill would go muddy
   against the dark theme's own ground, whereas transparent inherits it. */
.mfx-action-btn-info, .mfx-action-btn-info:focus {
	background-color: transparent !important;
	border-color: var(--blue-500) !important;
	color: var(--blue-500) !important;
}
.mfx-action-btn-info:hover {
	background-color: var(--blue-500) !important;
	color: var(--white, #fff) !important;
}
.mfx-action-btn-info:hover .icon { filter: brightness(0) invert(1); }
/* Frappe's icons are dark SVGs; on a filled button they vanish into it. */
.mfx-action-btn .icon, .mfx-action-btn-alt .icon, .mfx-action-btn-danger .icon {
	filter: brightness(0) invert(1);
}
/* A dropdown group's caret is a pseudo-element, not an .icon. */
.mfx-action-btn.dropdown-toggle::after,
.mfx-action-btn-alt.dropdown-toggle::after { color: var(--white, #fff) !important; }
`;

const MFX_TONE_CLASS = {
	primary: "mfx-action-btn",
	info: "mfx-action-btn-info",
	alt: "mfx-action-btn-alt",
	danger: "mfx-action-btn-danger",
};
const MFX_ALL_TONE_CLASSES =
	"mfx-action-btn mfx-action-btn-info mfx-action-btn-alt mfx-action-btn-danger";

function mfx_inject_button_style() {
	if (document.getElementById(MFX_BTN_STYLE_ID)) return;
	$("<style>").attr("id", MFX_BTN_STYLE_ID).text(MFX_BTN_CSS).appendTo("head");
}

// Every painter routes through here so a tone is applied exactly one way, and so
// re-painting on a second refresh replaces the old tone rather than stacking on it.
function _mfx_apply($el, tone) {
	if (!$el || !$el.length || !MFX_TONE_CLASS[tone]) return;
	$el.removeClass("btn-default btn-secondary " + MFX_ALL_TONE_CLASSES)
		.addClass(MFX_TONE_CLASS[tone]);
}

// ── Form toolbar (top bar) ───────────────────────────────────────────────────

// A plain top-bar button, added with frm.add_custom_button(label, fn) and no group.
// Frappe keys frm.custom_buttons by the TRANSLATED label, so translate here too.
function mfx_paint_button(frm, label, tone) {
	mfx_inject_button_style();
	if (!frm || !frm.custom_buttons) return;
	_mfx_apply(frm.custom_buttons[__(label)], tone);
}

// A dropdown GROUP button -- frm.add_custom_button(label, fn, group) puts the
// action inside a group whose own toggle is what the user sees and clicks.
// Colouring the group means colouring that toggle, not the dropdown items.
function mfx_paint_group(frm, group_label, tone) {
	mfx_inject_button_style();
	if (!frm || !frm.page || !frm.page.get_inner_group_button) return;
	let $group = frm.page.get_inner_group_button(__(group_label));
	if (!$group || !$group.length) return;
	_mfx_apply($group.find("button").first(), tone);
}

// ── Child-table grid toolbars ────────────────────────────────────────────────

// Grid buttons are keyed by the label they were added with, and that key usually
// carries an icon prefix (frappe.utils.icon(...) + " " + __("View All")) -- so
// match on the label CONTAINING the text, never on equality.
//
// `tones` is {tone: [substrings]}, e.g. {primary: ["Reserve"], alt: ["Unreserve"]}.
// A button matching nothing is left grey on purpose: Download/Upload sit on these
// same toolbars and are housekeeping, not actions to draw the eye to.
//
// Order matters where one label contains another: "Unreserve" contains "reserve",
// so alt is tested first and wins.
function mfx_paint_grid(frm, fieldname, tones) {
	mfx_inject_button_style();
	let grid = frm.fields_dict[fieldname] && frm.fields_dict[fieldname].grid;
	if (!grid || !grid.custom_buttons) return;
	Object.keys(grid.custom_buttons).forEach(function (label) {
		let $btn = grid.custom_buttons[label];
		if (!$btn || !$btn.length) return;
		for (let tone of ["danger", "alt", "info", "primary"]) {
			let needles = tones[tone] || [];
			if (needles.some((t) => label.indexOf(t) !== -1)) {
				_mfx_apply($btn, tone);
				return;
			}
		}
	});
}

// ── Inline Button fields (fieldtype "Button" on the form itself) ─────────────

// The control's own <input>/<button> element, e.g. Material Planning's
// "Check Stock Availability". Optionally re-labels it with an icon at the same
// time, which is what every existing caller wanted to do anyway.
function mfx_paint_field(frm, fieldname, tone, icon, label) {
	mfx_inject_button_style();
	let fd = frm.fields_dict[fieldname];
	let $btn = fd && fd.$input;
	if (!$btn || !$btn.length) return;
	if (label) $btn.html((icon ? frappe.utils.icon(icon, "sm") + "&nbsp;" : "") + __(label));
	_mfx_apply($btn, tone);
}

// ── Loose DOM buttons ────────────────────────────────────────────────────────

// For buttons built by hand with $('<button class="btn btn-sm btn-default">'),
// as the Sales Order client script and several grid headers do.
function mfx_paint_el($el, tone) {
	mfx_inject_button_style();
	_mfx_apply($el, tone);
}

window.mfx_inject_button_style = mfx_inject_button_style;
window.mfx_paint_button = mfx_paint_button;
window.mfx_paint_group = mfx_paint_group;
window.mfx_paint_grid = mfx_paint_grid;
window.mfx_paint_field = mfx_paint_field;
window.mfx_paint_el = mfx_paint_el;
