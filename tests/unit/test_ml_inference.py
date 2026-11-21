import asyncio
import threading
import time

import pytest

from supportflow_ai.adapters.classifiers.ml.inference import BoundedInference
from supportflow_ai.domain.errors import ProviderUnavailableError


def _runner(**overrides) -> BoundedInference:
    options = {"max_concurrency": 1, "max_queue": 0, "queue_timeout_s": 1.0}
    options.update(overrides)
    return BoundedInference(**options)


async def test_runs_off_the_event_loop_thread():
    runner = _runner()
    try:
        name = await runner.run(lambda: threading.current_thread().name)
    finally:
        runner.close()
    assert name.startswith("classifier-inference")
    assert runner.admitted == 0


async def test_event_loop_keeps_serving_while_inference_runs():
    runner = _runner()
    order: list[str] = []

    def slow_inference():
        time.sleep(0.2)
        order.append("inference")

    async def health_probe():
        await asyncio.sleep(0.01)
        order.append("health")

    try:
        await asyncio.gather(runner.run(slow_inference), health_probe())
    finally:
        runner.close()
    assert order == ["health", "inference"]


async def test_rejects_immediately_when_running_and_queue_are_full():
    runner = _runner(max_concurrency=1, max_queue=0)
    release = threading.Event()
    try:
        first = asyncio.ensure_future(runner.run(release.wait, 5))
        await asyncio.sleep(0.05)
        with pytest.raises(ProviderUnavailableError, match="classifier_busy"):
            await runner.run(lambda: "second")
        release.set()
        assert await first is True
    finally:
        release.set()
        runner.close()


async def test_queued_request_times_out_and_frees_its_slot():
    runner = _runner(max_concurrency=1, max_queue=1, queue_timeout_s=0.1)
    release = threading.Event()
    try:
        first = asyncio.ensure_future(runner.run(release.wait, 5))
        await asyncio.sleep(0.05)
        with pytest.raises(ProviderUnavailableError, match="classifier_busy"):
            await runner.run(lambda: "queued")
        assert runner.admitted == 1
        release.set()
        assert await first is True
        assert await runner.run(lambda: "after") == "after"
    finally:
        release.set()
        runner.close()
    assert runner.admitted == 0


async def test_running_inference_is_awaited_past_the_queue_timeout():
    runner = _runner(queue_timeout_s=0.05)
    try:
        assert await runner.run(lambda: time.sleep(0.15) or "done") == "done"
    finally:
        runner.close()


async def test_inference_errors_propagate_and_release_the_slot():
    runner = _runner()

    def broken():
        raise RuntimeError("model failure")

    try:
        with pytest.raises(RuntimeError):
            await runner.run(broken)
        assert runner.admitted == 0
    finally:
        runner.close()


@pytest.mark.parametrize(
    "options",
    [
        {"max_concurrency": 0},
        {"max_concurrency": 17},
        {"max_queue": -1},
        {"queue_timeout_s": 0},
        {"queue_timeout_s": 5.0},
    ],
)
def test_invalid_limits_are_rejected(options):
    with pytest.raises(ValueError):
        _runner(**options)
