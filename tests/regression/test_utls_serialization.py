# protects: Native JSON preparation consumes the original budget and cancellation prevents a later C call.
# fails_when: Serialization starts a fresh timeout or sends after the caller cancelled before native transmission.
# why_new: Admission/executor/body tests do not pause the actual native JSON encoder.
# seam: none
import asyncio
import threading

import httpx
import pytest

from tests.regression.test_utls_transport import native as native
from tests.regression.test_utls_transport import wait_started


@pytest.mark.parametrize("outcome", ["cancel", "expire", "remaining_budget"])
def test_native_serialization_keeps_original_deadline_and_cancel_boundary(native, monkeypatch, outcome):
    import aiograpi.utls as module

    async def scenario():
        entered, release = threading.Event(), threading.Event()
        original = module.json.dumps

        def held_encode(value, *args, **kwargs):
            if isinstance(value, dict) and "requestMethod" in value:
                entered.set()
                assert release.wait(2), "test did not release native request serialization"
            return original(value, *args, **kwargs)

        monkeypatch.setattr(module.json, "dumps", held_encode)
        transport = native.transport()
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            task = asyncio.create_task(
                client.post(
                    "https://fixture.invalid/", content=b"synthetic", timeout=0.03 if outcome == "expire" else 1
                )
            )
            try:
                await wait_started(entered)
                if outcome == "remaining_budget":
                    await asyncio.sleep(0.08)
                    release.set()
                    assert (await task).status_code == 200
                    assert 1 <= native.payloads[0]["timeoutMilliseconds"] < 950
                else:
                    if outcome == "cancel":
                        task.cancel()
                    with pytest.raises(asyncio.CancelledError if outcome == "cancel" else httpx.ConnectTimeout):
                        await task
            finally:
                release.set()
                await asyncio.gather(task, return_exceptions=True)
                await transport.aclose()
        assert len(native.payloads) == int(outcome == "remaining_budget")

    asyncio.run(scenario())
