import beacon_core


def test_version_defaults_to_dev():
    assert beacon_core.VERSION == "dev"
