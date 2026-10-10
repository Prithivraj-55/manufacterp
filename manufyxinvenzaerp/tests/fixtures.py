"""Records the unit tests need to exist on whatever site they run on.

The CI site is brand new -- its Item Group tree is only the setup wizard's (see
install_fixtures in .github/workflows/main.yml) -- while a developer's site is a copy
of live. Anything a test needs is asked for here, by what it is rather than by a name
one of those sites happens to have.
"""

import frappe
from frappe.utils.nestedset import get_root_of

TEST_ITEM_GROUP = "ZZTEST Items"


def ensure_test_item_group():
    """A leaf Item Group under the root, for Items a test creates.

    Item Group is mandatory on an Item and must not be a group node; a test that left
    it out failed in setUpClass on the CI site with "Value missing for Item: Item Group".
    """
    if not frappe.db.exists("Item Group", TEST_ITEM_GROUP):
        frappe.get_doc({
            "doctype": "Item Group",
            "item_group_name": TEST_ITEM_GROUP,
            "parent_item_group": get_root_of("Item Group"),
            "is_group": 0,
        }).insert(ignore_permissions=True)
    return TEST_ITEM_GROUP
