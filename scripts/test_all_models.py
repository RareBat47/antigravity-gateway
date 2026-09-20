"""
AGW Model Connectivity Test -- tests all 7 Hermes providers against the live gateway.
Run with: python scripts/test_all_models.py
"""

import asyncio
import json
import sys
import time
import httpx

GATEWAY = "http://127.0.0.1:8999"

PROVIDERS = [
    {
        "name": "Planning",
        "api_key": "agw-plan-claude-9x82",
        "model": "claude-opus-4-6-thinking",
        "family": "claude",
        "role": "Deep architectural reasoning & long-horizon planning",
    },
    {
        "name": "Coding-1",
        "api_key": "agw-code-gemini-1-7b41",
        "model": "gemini-3.6-flash-medium",
        "family": "gemini",
        "role": "High-volume implementation, quick iterations",
    },
    {
        "name": "Coding-2",
        "api_key": "agw-code-gemini-2-3f19",
        "model": "gemini-3.7-flash-medium",
        "family": "gemini",
        "role": "General coding + agentic work",
    },
    {
        "name": "Coding-3",
        "api_key": "agw-code-gemini-3-8d52",
        "model": "gemini-3.8-flash-high",
        "family": "gemini",
        "role": "Difficult implementation, refactors, multi-file reasoning",
    },
    {
        "name": "Hybrid-1",
        "api_key": "agw-code-hybrid-1-4a29",
        "model": "gemini-3.1-pro-low",
        "family": "gemini",
        "role": "Strong Google Pro deep reasoning path",
    },
    {
        "name": "Hybrid-2",
        "api_key": "agw-code-hybrid-2-6e83",
        "model": "claude-sonnet-4-6",
        "family": "claude",
        "role": "Independent Claude coding & thinking path",
    },
    {
        "name": "Debugging",
        "api_key": "agw-debug-all-9c37",
        "model": "gpt-oss-120b-medium",
        "family": "gpt",
        "role": "Root-cause analysis, complex bug diagnosis",
    },
]

TOOL_TEST_PROVIDER = {
    "name": "Coding-3",
    "api_key": "agw-code-gemini-3-8d52",
    "model": "gemini-3.8-flash-high",
}

SAMPLE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_file_content",
        "description": "Read a file from disk",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
            },
            "required": ["path"],
        },
    },
}


def p(*args, **kwargs):
    """Print flushed — ensures output appears even in subprocess capture."""
    print(*args, flush=True, **kwargs)


async def test_provider(client: httpx.AsyncClient, prov: dict, stream: bool = False) -> dict:
    headers = {
        "Authorization": f"Bearer {prov['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": prov["model"],
        "messages": [{"role": "user", "content": "Reply with exactly the word: ONLINE"}],
        "max_tokens": 300,
        "stream": stream,
    }
    start = time.time()
    result = {
        "provider": prov["name"],
        "model": prov["model"],
        "family": prov.get("family", "?"),
        "stream": stream,
        "ok": False,
        "status_code": None,
        "latency_ms": None,
        "response_text": None,
        "error": None,
        "account_used": None,
        "tokens": None,
        "finish_reason": None,
    }
    try:
        if stream:
            collected = []
            finish = None
            async with client.stream(
                "POST",
                f"{GATEWAY}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0,
            ) as resp:
                result["status_code"] = resp.status_code
                result["account_used"] = resp.headers.get("x-agw-account", "?")
                if resp.status_code == 200:
                    async for line in resp.aiter_lines():
                        if line.startswith("data:"):
                            d = line[5:].strip()
                            if d == "[DONE]":
                                break
                            try:
                                chunk = json.loads(d)
                                delta = chunk["choices"][0]["delta"].get("content", "")
                                if delta:
                                    collected.append(delta)
                                fr = chunk["choices"][0].get("finish_reason")
                                if fr:
                                    finish = fr
                                if "usage" in chunk:
                                    result["tokens"] = chunk["usage"]
                            except Exception:
                                pass
                    result["response_text"] = "".join(collected).strip()
                    result["ok"] = bool(result["response_text"]) or finish in ("stop", "tool_calls")
                    result["finish_reason"] = finish
                else:
                    body = await resp.aread()
                    result["error"] = body.decode(errors="replace")[:300]
        else:
            resp = await client.post(
                f"{GATEWAY}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            result["status_code"] = resp.status_code
            result["account_used"] = resp.headers.get("x-agw-account", "?")
            if resp.status_code == 200:
                data = resp.json()
                result["response_text"] = data["choices"][0]["message"]["content"].strip()
                result["ok"] = bool(result["response_text"])
                result["tokens"] = data.get("usage")
                result["finish_reason"] = data["choices"][0].get("finish_reason")
            else:
                result["error"] = resp.text[:300]
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["latency_ms"] = round((time.time() - start) * 1000)
    return result


async def test_tool_calling(client: httpx.AsyncClient) -> dict:
    """Test tool-call support on Coding-3 (streaming)."""
    prov = TOOL_TEST_PROVIDER
    headers = {
        "Authorization": f"Bearer {prov['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": prov["model"],
        "messages": [{"role": "user", "content": "Call get_file_content with path='README.md'"}],
        "tools": [SAMPLE_TOOL],
        "tool_choice": "auto",
        "stream": True,
        "max_tokens": 64,
    }
    result = {
        "provider": prov["name"],
        "model": prov["model"],
        "test": "tool_calling",
        "ok": False,
        "status_code": None,
        "latency_ms": None,
        "tool_called": None,
        "finish_reason": None,
        "error": None,
        "account_used": None,
    }
    start = time.time()
    try:
        tool_calls_seen = []
        async with client.stream(
            "POST",
            f"{GATEWAY}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60.0,
        ) as resp:
            result["status_code"] = resp.status_code
            result["account_used"] = resp.headers.get("x-agw-account", "?")
            if resp.status_code == 200:
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        d = line[5:].strip()
                        if d == "[DONE]":
                            break
                        try:
                            chunk = json.loads(d)
                            tcs = chunk["choices"][0]["delta"].get("tool_calls", [])
                            fr = chunk["choices"][0].get("finish_reason")
                            if fr:
                                result["finish_reason"] = fr
                            for tc in tcs:
                                fn_name = tc.get("function", {}).get("name")
                                if fn_name:
                                    tool_calls_seen.append(fn_name)
                        except Exception:
                            pass
                result["tool_called"] = tool_calls_seen[0] if tool_calls_seen else None
                result["ok"] = bool(tool_calls_seen)
            else:
                body = await resp.aread()
                result["error"] = body.decode(errors="replace")[:300]
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["latency_ms"] = round((time.time() - start) * 1000)
    return result


async def test_wrong_family(client: httpx.AsyncClient) -> dict:
    """Coding-1 (gemini-only key) should reject a claude model request with 403."""
    headers = {"Authorization": "Bearer agw-code-gemini-1-7b41", "Content-Type": "application/json"}
    payload = {
        "model": "claude-opus-4-6-thinking",
        "messages": [{"role": "user", "content": "test"}],
        "max_tokens": 5,
    }
    try:
        resp = await client.post(
            f"{GATEWAY}/v1/chat/completions", headers=headers, json=payload, timeout=10.0
        )
        return {
            "test": "key_family_restriction",
            "ok": resp.status_code == 403,
            "status_code": resp.status_code,
            "body": resp.text[:200],
        }
    except Exception as exc:
        return {"test": "key_family_restriction", "ok": False, "error": str(exc)}


def print_results(results, label):
    p(f"\n-- {label} " + "-" * (62 - len(label)))
    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        resp = (r["response_text"] or "")[:45].replace("\n", " ")
        tok_str = ""
        if r.get("tokens"):
            tok = r["tokens"]
            tok_str = f"  [in={tok.get('prompt_tokens',0)} out={tok.get('completion_tokens',0)}]"
        p(f"  [{status}] [{r['status_code']}] {r['provider']:<12} {r['model']:<30} {r['latency_ms']}ms{tok_str}")
        if resp:
            p(f"           reply: {repr(resp)}")
        if r.get("error"):
            p(f"           ERROR: {r['error'][:100]}")


async def main():
    p("\n" + "=" * 70)
    p("  ANTIGRAVITY GATEWAY -- FULL MODEL CONNECTIVITY TEST")
    p(f"  Gateway: {GATEWAY}")
    p(f"  Time:    {time.strftime('%Y-%m-%d %H:%M:%S')}")
    p("=" * 70)

    async with httpx.AsyncClient() as client:
        # Verify gateway is up
        try:
            health = await client.get(f"{GATEWAY}/health", timeout=5.0)
            p(f"\n  Gateway health: HTTP {health.status_code}  {health.text[:100]}")
        except Exception as exc:
            p(f"\n  ERROR: Cannot reach gateway: {exc}")
            return 1

        p("\n  Running all 7 providers (streaming + non-streaming + tool call + ACL)...")
        p("  This may take 30-90s depending on model latency.\n")

        # Run streaming tests for all 7 in parallel
        stream_results = await asyncio.gather(
            *[test_provider(client, prov, stream=True) for prov in PROVIDERS]
        )

        # Run non-streaming tests for all 7 in parallel
        nstream_results = await asyncio.gather(
            *[test_provider(client, prov, stream=False) for prov in PROVIDERS]
        )

        # Tool call test
        tool_result = await test_tool_calling(client)

        # ACL restriction test
        acl_result = await test_wrong_family(client)

    print_results(stream_results, "STREAMING")
    print_results(nstream_results, "NON-STREAMING")

    p("\n-- TOOL CALLING TEST " + "-" * 48)
    p(f"  [{'PASS' if tool_result['ok'] else 'FAIL'}] [{tool_result['status_code']}]"
      f" {tool_result['provider']}/{tool_result['model']}")
    p(f"         tool_called={tool_result['tool_called']}"
      f"  finish={tool_result.get('finish_reason')}"
      f"  latency={tool_result['latency_ms']}ms"
      f"  account={tool_result['account_used']}")
    if tool_result.get("error"):
        p(f"         ERROR: {tool_result['error'][:100]}")

    p("\n-- KEY FAMILY RESTRICTION TEST " + "-" * 38)
    p(f"  [{'PASS' if acl_result['ok'] else 'FAIL'}]"
      f" Coding-1 key + claude model -> expect 403 -> got {acl_result.get('status_code')}")
    if "error" in acl_result:
        p(f"         ERROR: {acl_result['error']}")

    # Summary
    all_stream_ok = all(r["ok"] for r in stream_results)
    all_nstream_ok = all(r["ok"] for r in nstream_results)
    all_good = all_stream_ok and all_nstream_ok and tool_result["ok"] and acl_result["ok"]
    stream_pass = sum(r["ok"] for r in stream_results)
    nstream_pass = sum(r["ok"] for r in nstream_results)

    p("\n" + "=" * 70)
    p(f"  OVERALL:       {'ALL TESTS PASSED' if all_good else 'SOME TESTS FAILED'}")
    p(f"  Streaming:     {'OK' if all_stream_ok else 'FAIL'}  ({stream_pass}/7 passed)")
    p(f"  Non-Streaming: {'OK' if all_nstream_ok else 'FAIL'}  ({nstream_pass}/7 passed)")
    p(f"  Tool Calling:  {'OK' if tool_result['ok'] else 'FAIL'}")
    p(f"  ACL Guard:     {'OK' if acl_result['ok'] else 'FAIL'}")
    p("=" * 70 + "\n")

    # Per-provider summary table
    p("  Provider      | Model                          | Stream | Non-Stream | Latency(s)")
    p("  " + "-" * 80)
    for sr, nr in zip(stream_results, nstream_results):
        sp = "PASS" if sr["ok"] else "FAIL"
        np = "PASS" if nr["ok"] else "FAIL"
        lat_s = f"{sr['latency_ms']/1000:.1f}s / {nr['latency_ms']/1000:.1f}s"
        p(f"  {sr['provider']:<14}| {sr['model']:<31}| {sp:<7}| {np:<11}| {lat_s}")

    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
