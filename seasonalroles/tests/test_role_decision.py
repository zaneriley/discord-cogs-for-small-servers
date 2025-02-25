import os
import sys

import pytest

# Add the module directory to the Python path
module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if module_dir not in sys.path:
    sys.path.insert(0, module_dir)

from cogs.seasonalroles.role.role_decision import decide_role_action


class FakeRole:
    def __init__(self, name):
        self.name = name

    def lower(self):
        return self.name.lower()


@pytest.mark.parametrize(
    ("holiday_name", "date", "roles", "expected"),
    [
        (
            "Kids Day",
            "05-05",
            [FakeRole("Kids Day Old"), FakeRole("Other Role")],
            ("update", "Kids Day 05-05"),
        ),
        (
            "Kids Day",
            "05-05",
            ["Kids Day Anniversary", "Another Role"],
            ("update", "Kids Day 05-05"),
        ),
        (
            "Kids Day",
            "05-05",
            ["Random Role", "Other Role"],
            ("create", "Kids Day 05-05"),
        ),
        (
            "Kids Day",
            "05-05",
            ["kids day special", "Yet Another Role"],
            ("update", "Kids Day 05-05"),
        ),
    ],
)
def test_decide_role_action(holiday_name, date, roles, expected):
    action, role_name = decide_role_action(holiday_name, date, roles)
    assert (action, role_name) == expected
