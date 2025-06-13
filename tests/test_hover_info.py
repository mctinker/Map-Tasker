import unittest
from unittest.mock import MagicMock, patch


class TestDisplayHoverInfo(unittest.TestCase):
    def setUp(self):
        """Set up a mock GUI environment before each test."""
        self.mock_gui = MagicMock()
        self.mock_gui.master = MagicMock()
        self.mock_gui.master.master = MagicMock()

        # Mock the structure of items_for_selection
        self.mock_gui.master.master.items_for_selection = {
            "task_1": {"name": "Task One", "item": "task"},
            "profile_1": {"name": "Profile One", "item": "profile"},
            "scene_1": {"name": "Scene One", "item": "scene"},
            "project_1": {"name": "Project One", "item": "project"},
        }

        # Create the class instance
        self.instance = MagicMock()
        self.instance.master = self.mock_gui.master
        self.instance.hover_task = MagicMock(return_value="Task: Task One (Details)")
        self.instance.hover_profile = MagicMock(return_value="Profile: Profile One (Details)")
        self.instance.hover_scene = MagicMock(return_value="Scene: Scene One (Details)")
        self.instance.hover_project = MagicMock(return_value="Project: Project One (Details)")
        self.instance.hover_tooltip = None

    @patch("tkinter.Label")
    def test_display_hover_info_task(self, mock_label):
        """Test display_hover_info for a task item."""
        event = MagicMock(x=50, y=50)
        self.instance.display_hover_info("task_1", event)

        self.instance.hover_task.assert_called_once_with("task_1", "Task One", "Task: Task One")
        mock_label.assert_called_once_with(
            self.instance,
            text="Task: Task One (Details)",
            bg="#092944",
            justify="left",
            font=("Courier", 12),
            padx=5,
            pady=5,
        )

    @patch("tkinter.Label")
    def test_display_hover_info_profile(self, mock_label):
        """Test display_hover_info for a profile item."""
        event = MagicMock(x=50, y=50)
        self.instance.display_hover_info("profile_1", event)

        self.instance.hover_profile.assert_called_once_with("Profile One", "Profile: Profile One")
        mock_label.assert_called_once_with(
            self.instance,
            text="Profile: Profile One (Details)",
            bg="#092944",
            justify="left",
            font=("Courier", 12),
            padx=5,
            pady=5,
        )

    @patch("tkinter.Label")
    def test_display_hover_info_scene(self, mock_label):
        """Test display_hover_info for a scene item."""
        event = MagicMock(x=50, y=50)
        self.instance.display_hover_info("scene_1", event)

        self.instance.hover_scene.assert_called_once_with("Scene One", "Scene: Scene One")
        mock_label.assert_called_once_with(
            self.instance,
            text="Scene: Scene One (Details)",
            bg="#092944",
            justify="left",
            font=("Courier", 12),
            padx=5,
            pady=5,
        )

    @patch("tkinter.Label")
    def test_display_hover_info_project(self, mock_label):
        """Test display_hover_info for a project item."""
        event = MagicMock(x=50, y=50)
        self.instance.display_hover_info("project_1", event)

        self.instance.hover_project.assert_called_once_with("Project One", "Project: Project One")
        mock_label.assert_called_once_with(
            self.instance,
            text="Project: Project One (Details)",
            bg="#092944",
            justify="left",
            font=("Courier", 12),
            padx=5,
            pady=5,
        )

    def test_display_hover_info_invalid_tag(self):
        """Test that no tooltip is created when an invalid tag is used."""
        event = MagicMock(x=50, y=50)
        self.instance.display_hover_info("invalid_tag", event)

        self.assertIsNone(self.instance.hover_tooltip)
        self.instance.hover_task.assert_not_called()
        self.instance.hover_profile.assert_not_called()
        self.instance.hover_scene.assert_not_called()
        self.instance.hover_project.assert_not_called()


if __name__ == "__main__":
    unittest.main()
