from datetime import datetime, timezone

import jinja2

import lair


def fill(prompt_template):
    template = jinja2.Template(prompt_template)

    utc_now = datetime.now(timezone.utc)

    context = {
        "date": utc_now.strftime("%Y-%m-%d UTC"),
        "datetime": utc_now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "get_config": lambda k: lair.config.get(k),
    }

    return template.render(context)
