import unittest

from maptasker.src.profiles import set_name_to_condition


class TestSetNameToCondition(unittest.TestCase):
    def test_empty_conditions(self):
        profile_conditions = ""
        profile_name = "MyProfile"
        profile_name_with_html = "<em>Profile: MyProfile</em>"
        expected_html = "<em>Profile: MyProfile</em>"
        expected_name = "MyProfile"
        actual_html, actual_name = set_name_to_condition(
            profile_conditions,
            profile_name,
            profile_name_with_html,
        )
        self.assertEqual(actual_html, expected_html)
        self.assertEqual(actual_name, expected_name)

    def test_with_event_condition(self):
        profile_conditions = "Event: Notification"
        profile_name = "No Profile"
        profile_name_with_html = "<em>Profile: No Profile</em>"
        expected_html = "<em>Profile: *Notification (No Profile)</em>"
        expected_name = "*Notification (No Profile)"
        actual_html, actual_name = set_name_to_condition(
            profile_conditions,
            profile_name,
            profile_name_with_html,
        )
        self.assertEqual(actual_html, expected_html)
        self.assertEqual(actual_name, expected_name)

    def test_with_multiple_conditions(self):
        profile_conditions = "Event: Notification, State: Battery Level"
        profile_name = "No Profile"
        profile_name_with_html = "<em>Profile: No Profile</em>"
        expected_html = "<em>Profile: *NotificationState  (No Profile)</em>"
        expected_name = "*NotificationState  (No Profile)"
        actual_html, actual_name = set_name_to_condition(
            profile_conditions,
            profile_name,
            profile_name_with_html,
        )
        self.assertEqual(actual_html, expected_html)
        self.assertEqual(actual_name, expected_name)

    def test_with_priority(self):
        profile_conditions = "Event: Notification, Priority: 5"
        profile_name = "No Profile"
        profile_name_with_html = "<em>Profile: No Profile</em>"
        expected_html = "<em>Profile: *Notification (No Profile)</em>"
        expected_name = "*Notification (No Profile)"
        actual_html, actual_name = set_name_to_condition(
            profile_conditions,
            profile_name,
            profile_name_with_html,
        )
        self.assertEqual(actual_html, expected_html)
        self.assertEqual(actual_name, expected_name)

    def test_with_equals_in_condition(self):
        profile_conditions = "Event: SMS Received, From:=:="
        profile_name = "No Profile"
        profile_name_with_html = "<em>Profile: No Profile</em>"
        expected_html = "<em>Profile: *SMS Received From (No Profile)</em>"
        expected_name = "*SMS Received From (No Profile)"
        actual_html, actual_name = set_name_to_condition(
            profile_conditions,
            profile_name,
            profile_name_with_html,
        )
        self.assertEqual(actual_html, expected_html)
        self.assertEqual(actual_name, expected_name)


if __name__ == "__main__":
    unittest.main()
