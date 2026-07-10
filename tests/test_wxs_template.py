import re
import unittest
from pathlib import Path


TEMPLATE = Path("{{ cookiecutter.format }}/{{ cookiecutter.app_name }}.wxs")


class ShortcutDescriptionTests(unittest.TestCase):
    def test_shortcut_description_is_strictly_limited(self):
        """Shortcut descriptions must fit within WiX's 256-character limit."""
        wxs_template = TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            "{%- set description = cookiecutter.description[:256] %}",
            wxs_template,
        )

    def test_shortcuts_use_limited_description(self):
        """Start menu and desktop shortcuts use the limited description."""
        wxs_template = TEMPLATE.read_text(encoding="utf-8")

        shortcut_descriptions = re.findall(
            r"<Shortcut\b(?:(?!</?Shortcut\b).)*?Description=\"([^\"]+)\"",
            wxs_template,
            flags=re.DOTALL,
        )

        self.assertEqual(shortcut_descriptions, ["{{ description }}"] * 2)


if __name__ == "__main__":
    unittest.main()
