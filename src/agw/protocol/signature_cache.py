"""Thread-safe TTL cache for Gemini thought_signatures across conversation turns."""

import collections
import hashlib
import json
import re
import time
from typing import Any, Dict, Optional


class ThoughtSignatureCache:
    """
    Caches cryptographic thought_signatures produced by Gemini during tool calls.
    Allows downstream clients (like Hermes, OpenAI SDK, LiteLLM) that strip or normalize
    tool_call objects to recover the exact upstream signature when sending tool results back.
    """

    def __init__(self, max_size: int = 5000, ttl_seconds: float = 3600.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        # Maps key -> (signature, expiry_timestamp)
        self._cache: Dict[str, tuple[str, float]] = {}
        # Ring buffer of recent signatures (signature, timestamp)
        self._recent_signatures: collections.deque = collections.deque(maxlen=100)

    def _purge_expired(self) -> None:
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._cache.items() if now > exp]
        for k in expired_keys:
            self._cache.pop(k, None)

    @staticmethod
    def _normalize_args(args: Any) -> str:
        if isinstance(args, dict):
            try:
                return json.dumps(args, sort_keys=True)
            except Exception:
                return str(args)
        elif isinstance(args, str):
            try:
                parsed = json.loads(args)
                if isinstance(parsed, dict):
                    return json.dumps(parsed, sort_keys=True)
            except Exception:
                pass
            return args.strip()
        return str(args)

    @staticmethod
    def _args_hash(fn_name: str, args: Any) -> str:
        norm = ThoughtSignatureCache._normalize_args(args)
        key_str = f"{fn_name.strip().lower()}:{norm}"
        return f"content_{hashlib.sha256(key_str.encode('utf-8')).hexdigest()[:24]}"

    def store(
        self,
        call_id: Optional[str],
        signature: str,
        fn_name: Optional[str] = None,
        args: Any = None,
    ) -> None:
        """Store a thought signature indexed by call_id, normalized call_id, and content hash."""
        if not signature or not isinstance(signature, str):
            return

        now = time.time()
        exp = now + self.ttl_seconds

        if len(self._cache) >= self.max_size:
            self._purge_expired()
            if len(self._cache) >= self.max_size:
                # Evict oldest entry
                oldest_key = next(iter(self._cache))
                self._cache.pop(oldest_key, None)

        # 1. Store by exact call_id
        if call_id:
            cid = str(call_id).strip()
            self._cache[f"id_{cid}"] = (signature, exp)

            # Also strip trailing indices like _0, _1 if present
            # e.g. call_terminal_0 -> call_terminal
            stripped_id = re.sub(r"_\d+$", "", cid)
            if stripped_id != cid:
                self._cache[f"id_{stripped_id}"] = (signature, exp)

            # Strip call_ prefix if present
            if cid.startswith("call_"):
                self._cache[f"id_{cid[5:]}"] = (signature, exp)

        # 2. Store by function name + args content hash
        if fn_name:
            c_hash = self._args_hash(fn_name, args)
            self._cache[c_hash] = (signature, exp)
            # Also store by fn_name alone (most recent for this tool)
            self._cache[f"fn_{fn_name.strip().lower()}"] = (signature, exp)

        # 3. Add to recent deque
        self._recent_signatures.append((signature, now))

    def get(self, call_id: Optional[str]) -> Optional[str]:
        """Retrieve signature by call_id or normalized call_id."""
        if not call_id:
            return None

        now = time.time()
        cid = str(call_id).strip()

        # Try exact id
        for key in [
            f"id_{cid}",
            f"id_{re.sub(r'_\d+$', '', cid)}",
            f"id_{cid[5:]}" if cid.startswith("call_") else None,
            f"id_{cid[3:]}" if cid.startswith("fc_") else None,
        ]:
            if key and key in self._cache:
                sig, exp = self._cache[key]
                if now <= exp:
                    return sig
                else:
                    self._cache.pop(key, None)

        return None

    def get_by_call(self, fn_name: Optional[str], args: Any = None) -> Optional[str]:
        """Retrieve signature by function name and arguments content hash."""
        if not fn_name:
            return None

        now = time.time()
        c_hash = self._args_hash(fn_name, args)
        if c_hash in self._cache:
            sig, exp = self._cache[c_hash]
            if now <= exp:
                return sig
            else:
                self._cache.pop(c_hash, None)

        # Fallback to most recent call for this function name
        fn_key = f"fn_{fn_name.strip().lower()}"
        if fn_key in self._cache:
            sig, exp = self._cache[fn_key]
            if now <= exp:
                return sig
            else:
                self._cache.pop(fn_key, None)

        return None

    def get_latest(self) -> Optional[str]:
        """Retrieve the most recently observed thought signature."""
        now = time.time()
        while self._recent_signatures:
            sig, ts = self._recent_signatures[-1]
            if now - ts <= self.ttl_seconds:
                return sig
            self._recent_signatures.pop()
        return None

    def clear(self) -> None:
        self._cache.clear()
        self._recent_signatures.clear()


# Global singleton instance
thought_signature_cache = ThoughtSignatureCache()
