from __future__ import annotations

import pytest

from tests.helpers import stub_optional_dependencies

stub_optional_dependencies()


def pytest_collection_modifyitems(config, items):
    """Apply the ``unit`` marker to tests that do not opt into ``integration``.

    Args:
        config: Pytest configuration object.
        items: Collected test items to mutate.
    """
    for item in items:
        if "integration" not in item.keywords:
            item.add_marker(pytest.mark.unit)
