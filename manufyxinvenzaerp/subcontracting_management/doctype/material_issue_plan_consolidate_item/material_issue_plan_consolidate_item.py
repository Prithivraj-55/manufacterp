# Copyright (c) 2026, Manufyxinvenza and Contributors
# License: GNU General Public License v3. See license.txt

from frappe.model.document import Document


class MaterialIssuePlanConsolidateItem(Document):
	"""One physical thing to move: an item in a specific batch.

	Every field is read-only and derived -- see _sync_consolidate_items in
	material_issue_plan.py for how the rows are built."""
	pass
