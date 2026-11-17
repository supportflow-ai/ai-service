"""Chạy suy luận CPU ngoài event loop, có giới hạn song song (ml-classifier-plan.md K1).

`TicketClassifier.classify` là `async`. Gọi thẳng mô hình trong `async def` sẽ chặn event loop, mọi
request khác (kể cả `/health/*`) phải chờ. Adapter `ml` gọi `BoundedInference.run` thay vào đó.

Vì sao xếp hàng có giới hạn thay vì từ chối ngay khi đầy chỗ: adapter của Backend
(`HttpTicketClassificationService`) retry một lần sau 100 ms khi gặp 503 và tính mỗi lần thất bại
vào `ClassificationCircuit` (3 lỗi liên tiếp thì ngắt 30 s cho mọi phiếu). Từ chối ngay khi có vài
phiếu đến cùng lúc dễ làm mở ngắt mạch. Ở đây request được chờ trong hàng có độ sâu `max_queue`,
tối đa `queue_timeout_s` (nhỏ hơn ngân sách 5 s của Backend); quá giới hạn mới trả 503
`classifier_busy`.

Dùng executor riêng (không dùng thread pool mặc định) để suy luận không tranh luồng với phần khác,
và không gắn với event loop cụ thể nào. Hàm suy luận phải an toàn khi gọi từ nhiều luồng.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TypeVar

from supportflow_ai.domain.errors import ProviderUnavailableError

T = TypeVar("T")

MAX_CONCURRENCY_LIMIT = 16
MAX_QUEUE_LIMIT = 256
# Backend chờ mặc định 5 s (cấu hình 1–30 s); chừa thời gian cho suy luận và mạng.
MAX_QUEUE_TIMEOUT_S = 4.0


class BoundedInference:
    def __init__(
        self, *, max_concurrency: int, max_queue: int, queue_timeout_s: float,
    ) -> None:
        if not 1 <= max_concurrency <= MAX_CONCURRENCY_LIMIT:
            raise ValueError(f"max_concurrency must be in [1, {MAX_CONCURRENCY_LIMIT}]")
        if not 0 <= max_queue <= MAX_QUEUE_LIMIT:
            raise ValueError(f"max_queue must be in [0, {MAX_QUEUE_LIMIT}]")
        if not 0.0 < queue_timeout_s <= MAX_QUEUE_TIMEOUT_S:
            raise ValueError(f"queue_timeout_s must be in (0, {MAX_QUEUE_TIMEOUT_S}]")
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrency, thread_name_prefix="classifier-inference",
        )
        self._capacity = max_concurrency + max_queue
        self._queue_timeout_s = queue_timeout_s
        self._admitted = 0
        self._lock = threading.Lock()

    @property
    def admitted(self) -> int:
        """Số tác vụ đang chạy hoặc đang chờ trong executor."""
        with self._lock:
            return self._admitted

    async def run(self, fn: Callable[..., T], /, *args: object) -> T:
        with self._lock:
            if self._admitted >= self._capacity:
                raise ProviderUnavailableError("classifier_busy")
            self._admitted += 1
        try:
            task: Future[T] = self._executor.submit(fn, *args)
        except BaseException:
            self._release(None)
            raise
        # Trả chỗ khi tác vụ thực sự kết thúc hoặc bị hủy lúc còn trong hàng chờ.
        task.add_done_callback(self._release)
        waiter = asyncio.wrap_future(task)
        try:
            return await asyncio.wait_for(asyncio.shield(waiter), self._queue_timeout_s)
        except TimeoutError:
            if task.cancel():
                raise ProviderUnavailableError("classifier_busy") from None
            # Đã bắt đầu chạy: suy luận ngắn, chờ xong thay vì bỏ kết quả.
            return await waiter
        except asyncio.CancelledError:
            # Client ngắt kết nối: bỏ tác vụ nếu còn trong hàng chờ.
            task.cancel()
            raise

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _release(self, _task: Future | None) -> None:
        with self._lock:
            self._admitted -= 1
