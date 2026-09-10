"""
``ResilientStreamingResponse`` — a ``StreamingResponse`` that keeps draining
its body iterator to completion even after the client disconnects, instead
of Starlette's default behaviour of racing the stream against ``receive()``
and cancelling the iterator the moment a disconnect is observed.

Generation jobs need this because the actual work — and its persistence
into the ``generation_job`` row — happens as a *side effect* of iterating
``features/generation_jobs/service.py::stream_generation_job``'s body, not
just the bytes sent to the client. Cancelling that iterator on disconnect
would silently kill the job the exact way it did before the background-job
system was introduced (see that module's docstring for the history). Never
returning from this response's ASGI call until the run is actually done —
rather than as soon as the client goes away — is also what keeps the
server's CPU allocated for the whole run on infrastructure (e.g. Cloud Run)
that only guarantees CPU while a request is in flight; a detached
``BackgroundTasks`` callback that outlives the response has no such
guarantee there.

Send failures against an already-closed connection are swallowed — there is
nothing left to receive them — but the iterator (and therefore the DB writes
it performs) keeps running regardless.
"""
from __future__ import annotations

from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send


class ResilientStreamingResponse(StreamingResponse):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await send(
                {
                    "type": "http.response.start",
                    "status": self.status_code,
                    "headers": self.raw_headers,
                }
            )
        except Exception:
            pass

        async for chunk in self.body_iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode(self.charset)
            try:
                await send({"type": "http.response.body", "body": chunk, "more_body": True})
            except Exception:
                pass  # client gone — keep draining the iterator for its side effects

        try:
            await send({"type": "http.response.body", "body": b"", "more_body": False})
        except Exception:
            pass

        if self.background is not None:
            await self.background()
