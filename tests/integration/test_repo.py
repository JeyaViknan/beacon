"""Repository behaviour that the handlers rely on, especially the transactional guards."""

from datetime import UTC, datetime

import pytest

from beacon_core.models import CheckResult, Product, ProductInput
from beacon_core.repo_dynamo import ConflictError, DuplicateError, Repo
from beacon_core.state_machine import evaluate
from tests.conftest import product_item

RUN_AT = datetime(2026, 10, 24, 10, 0, tzinfo=UTC)


@pytest.fixture
def repo(aws) -> Repo:
    r = Repo(aws.table)
    r.create_product(Product.model_validate(product_item(openAfter=1)))
    return r


def result(ok: bool = False) -> CheckResult:
    return CheckResult(
        product_id="01PRODUCT",
        ok=ok,
        http_code=200 if ok else 502,
        latency_ms=90,
        error=None if ok else "HTTP 502",
    )


def test_concurrent_redelivery_is_caught_by_the_conditional_put(repo):
    """Two processors read the same product before either writes: only one may apply."""
    product = repo.get_product("01PRODUCT")
    ev = evaluate(product, "ap-south-1", result(), RUN_AT, incident_id="INC1")
    repo.apply_evaluation(product, "ap-south-1", result(), RUN_AT, ev)
    with pytest.raises(DuplicateError):
        repo.apply_evaluation(product, "ap-south-1", result(), RUN_AT, ev)
    assert len(repo.incidents_for("01PRODUCT")) == 1
    assert repo.get_product("01PRODUCT").version == 1


def test_stale_product_version_is_a_conflict(repo):
    stale = repo.get_product("01PRODUCT")
    ev1 = evaluate(stale, "ap-south-1", result(True), RUN_AT, incident_id="A")
    repo.apply_evaluation(stale, "ap-south-1", result(True), RUN_AT, ev1)
    # A second region's result evaluated against the old version must be retried.
    ev2 = evaluate(stale, "us-east-1", result(True), RUN_AT, incident_id="B")
    with pytest.raises(ConflictError):
        repo.apply_evaluation(stale, "us-east-1", result(True), RUN_AT, ev2)


def test_update_config_and_live_use_optimistic_locking(repo):
    product = repo.get_product("01PRODUCT")
    config = ProductInput.model_validate({**product.config().model_dump(), "name": "Renamed"})
    updated = repo.update_config(product, config, RUN_AT)
    assert updated.version == 1
    assert repo.get_product("01PRODUCT").name == "Renamed"
    with pytest.raises(ConflictError):
        repo.update_config(product, config, RUN_AT)  # still holding version 0
    with pytest.raises(ConflictError):
        repo.update_live(product, product.live(), RUN_AT)


def test_create_twice_and_delete_missing(repo):
    from botocore.exceptions import ClientError

    with pytest.raises(ClientError):
        repo.create_product(repo.get_product("01PRODUCT"))
    assert repo.delete_product("01PRODUCT") is True
    assert repo.delete_product("01PRODUCT") is False


def test_snapshot_merges_the_just_written_product(repo, aws):
    newcomer = Product.model_validate(product_item(id="NEW", name="Newcomer"))
    # Not written to the table at all: proves the snapshot does not depend on GSI freshness.
    repo.publish_snapshot(RUN_AT, changed=newcomer)
    ids = [m["id"] for m in repo.get_snapshot_item()["monitors"]]
    assert ids == ["01PRODUCT", "NEW"]
    repo.publish_snapshot(RUN_AT, deleted_id="01PRODUCT")
    assert repo.get_snapshot_item()["monitors"] == []


def test_save_acknowledged_refuses_non_open(repo, aws):
    from beacon_core.state_machine import acknowledge

    product = repo.get_product("01PRODUCT")
    ev = evaluate(product, "ap-south-1", result(), RUN_AT, incident_id="INC1")
    applied = repo.apply_evaluation(product, "ap-south-1", result(), RUN_AT, ev)
    incident = applied.incident
    acked = acknowledge(incident, RUN_AT)
    repo.save_acknowledged(acked)
    with pytest.raises(ConflictError):
        repo.save_acknowledged(acked)  # no longer OPEN


def test_throttle_roundtrip(repo):
    repo.put_throttle(3, None, RUN_AT)
    assert repo.get_throttle()["failures"] == 3
    repo.clear_throttle()
    assert repo.get_throttle() == {}
