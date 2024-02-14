# Copyright© 1986-2024 Altair Engineering Inc.

"""Extension to generate additional files as templates."""

from pkr.ext import ExtMixin
from pkr.kard import Kard
from pkr.utils import get_pkr_path


class BasicTemplate(ExtMixin):
    """pkr extension to configure generate extra files using templates.

    It is invoked during the make call.
    """

    @staticmethod
    def populate_kard():
        """Generate the template listed in the env."""

        kard = Kard.load_current()

        extra_templates = kard.env.get("templates", [])

        tpl_engine = kard.get_template_engine()

        for tpl in extra_templates:
            tpl_path = get_pkr_path() / tpl["template"]
            # Render the template
            tpl_render = tpl_engine.process_template(tpl_path)

            # Write it out
            dst = kard.path / tpl["dst"]
            dst.write_text(tpl_render)
