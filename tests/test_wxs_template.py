import re
import tempfile
import unittest
from pathlib import Path

from cookiecutter.main import cookiecutter

TEMPLATE_ROOT = Path(__file__).parent.parent

# WiX silently truncates a Shortcut's Description to 256 characters; anything
# longer corrupts the following attribute (the icon path). See
# https://github.com/beeware/briefcase/issues/2864.
WIX_DESCRIPTION_LIMIT = 256

# Fields that Briefcase normally supplies to the template as structured data
# rather than the placeholder strings in cookiecutter.json.
STRUCTURED_CONTEXT = {
    "document_types": {},
    "install_options": {},
    "uninstall_options": {},
}


def render_wxs(description):
    """Render the template with the given app description and return the
    ``Description`` attribute of every Shortcut in the generated ``.wxs``."""
    with tempfile.TemporaryDirectory() as output_dir:
        cookiecutter(
            str(TEMPLATE_ROOT),
            no_input=True,
            output_dir=output_dir,
            extra_context={**STRUCTURED_CONTEXT, "description": description},
        )
        (wxs,) = Path(output_dir).rglob("*.wxs")
        content = wxs.read_text(encoding="utf-8")

    return re.findall(
        r'<Shortcut\b[^>]*?Description="([^"]*)"', content, flags=re.DOTALL
    )


class ShortcutDescriptionTests(unittest.TestCase):
    def test_short_description_is_preserved(self):
        """A description within the limit is used verbatim."""
        description = "A short description"
        self.assertEqual(render_wxs(description), [description, description])

    def test_long_description_is_truncated(self):
        """A description in the 257-261 character range (which Jinja's default
        ``truncate`` leeway would let through) is capped at 256 characters."""
        descriptions = render_wxs("x" * 260)

        self.assertEqual(len(descriptions), 2)
        for description in descriptions:
            self.assertLessEqual(len(description), WIX_DESCRIPTION_LIMIT)


if __name__ == "__main__":
    unittest.main()
