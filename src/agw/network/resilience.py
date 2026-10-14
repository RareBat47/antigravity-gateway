"""Network Resilience Engine: Handles transient router disconnects, socket resets,
DNS lookup errors, and network unreachability without dropping OpenCode client requests.

Features:
- Identifies transient network / router drop exceptions.
- Holds open client HTTP/SSE connections while silently waiting for router reconnection (up to 90 seconds).
- Emits periodic SSE keep-alive comments (: keep-alive\\n\\n) to prevent OpenCode/client timeouts during router reboot.
- Automatically resumes upstream transmission as soon as connectivity returns.
"""

import asyncio
import logging
import socket
import ssl
import time
from typing import Any, AsyncIterator, Callable, Dict, Optional, Tuple
import httpx

logger = logging.getLogger("agw.network.resilience")

TRANSIENT_NETWORK_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
    socket.gaierror,
    ConnectionResetError,
    ConnectionRefusedError,
    BrokenPipeError,
    ssl.SSLError,
    OSError,
)


def is_transient_network_error(exc: Exception) -> bool:
    """Check if an exception is caused by a local or transient router / ISP network drop."""
    if isinstance(exc, TRANSIENT_NETWORK_EXCEPTIONS):
        return True
    msg = str(exc).lower()
    transient_phrases = [
        "network is unreachable",
        "name or service not known",
        "connection reset by peer",
        "temporary failure in name resolution",
        "connection refused",
        "failed to establish a new connection",
        "nodename nor servname provided",
        "socket.gaierror",
        "connection broken",
        "eof occurred in violation of protocol",
    ]
    return any(p in msg for p in transient_phrases)


async def wait_for_connectivity(max_wait_seconds: float = 60.0, check_interval: float = 2.0) -> bool:
    """Actively polls until upstream DNS or TCP handshake succeeds after a router disconnect."""
    start = time.time()
    targets = [
        ("8.8.8.8", 53),
        ("cloudcode-pa.googleapis.com", 443),
        ("generativelanguage.googleapis.com", 443),
    ]

    while (time.time() - start) < max_wait_seconds:
        for host, port in targets:
            try:
                # Fast socket connect check
                loop = asyncio.get_running_loop()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setblocking(False)
                await loop.sock_connect(sock, (host, port))
                sock.close()
                logger.info(f"Network connectivity confirmed via {host}:{port} after {round(time.time() - start, 1)}s")
                return True
            except Exception:
                pass
        await asyncio.sleep(check_interval)

    logger.warning(f"Network connectivity not restored after {max_wait_seconds}s")
    return False


class NetworkResilientStream:
    """Wraps an upstream streaming generator to survive temporary router disconnects."""

    def __init__(
        self,
        create_stream_fn: Callable[[], AsyncIterator[Tuple[int, str]]],
        max_reconnect_wait: float = 90.0,
        keepalive_interval: float = 3.0,
    ):
        self.create_stream_fn = create_stream_fn
        self.max_reconnect_wait = max_reconnect_wait
        self.keepalive_interval = keepalive_interval

    async def __aiter__(self) -> AsyncIterator[Tuple[int, str]]:
        stream_iter = self.create_stream_fn()
        start_wait = time.time()

        while True:
            try:
                async for status, line in stream_iter:
                    yield status, line
                return
            except Exception as e:
                if not is_transient_network_error(e):
                    yield 503, f"data: {{\"error\": \"{str(e)}\"}}\n\n"
                    return

                logger.warning(f"Transient network/router drop detected: {e}. Entering hold & auto-reconnect...")
                elapsed = time.time() - start_wait
                if elapsed >= self.max_reconnect_wait:
                    logger.error(f"Router disconnect exceeded max grace window ({self.max_reconnect_wait}s)")
                    yield 503, "data: {\"error\": \"Network connectivity lost. Router did not reconnect within grace window.\"}\n\n"
                    return

                # Hold open OpenCode's stream by sending SSE comment keep-alives so it never times out
                yield 200, ": keep-alive (waiting for network reconnection)\n\n"
                await asyncio.sleep(self.keepalive_interval)

                # Check if router came back
                reconnected = await wait_for_connectivity(max_wait_seconds=5.0, check_interval=1.0)
                if reconnected:
                    logger.info("Router reconnected! Resuming stream generation seamlessly...")
                    stream_iter = self.create_stream_fn()
