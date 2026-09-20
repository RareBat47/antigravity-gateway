"""
AGW Dedicated Hermes Test & Debug Harness
Tests all 7 models across:
  - Single-turn chat
  - Tool calling execution
  - Multi-turn thought_signature persistence
  - Streaming SSE output
  - Live Hermes CLI with worker profiles
"""

import asyncio
import json
import subprocess
import sys
import time
import httpx

GATEWAY = "http://127.0.0.1:8999"

MODELS = [
    {
        "role": "Planning",
        "key": "agw-plan-claude-9x82",
        "model": "claude-opus-4-6-thinking",
        "family": "claude",
    },
    {
        "role": "Coding-1",
        "key": "agw-code-gemini-1-7b41",
        "model": "gemini-3.6-flash-medium",
        "family": "gemini",
    },
    {
        "role": "Coding-2",
        "key": "agw-code-gemini-2-3f19",
        "model": "gemini-3.7-flash-medium",
        "family": "gemini",
    },
    {
        "role": "Coding-3",
        "key": "agw-code-gemini-3-8d52",
        "model": "gemini-3.8-flash-high",
        "family": "gemini",
    },
    {
        "role": "Hybrid-1",
        "key": "agw-code-hybrid-1-4a29",
        "model": "gemini-3.1-pro-low",
        "family": "gemini",
    },
    {
        "role": "Hybrid-2",
        "key": "agw-code-hybrid-2-6e83",
        "model": "claude-sonnet-4-6",
        "family": "claude",
    },
    {
        "role": "Debugging",
        "key": "agw-debug-all-9c37",
        "model": "gpt-oss-120b-medium",
        "family": "gpt",
    },
]

SAMPLE_TOOL = {
    "type": "function",
    "function": {
        "name": "system_info",
        "description": "Get operating system details and CPU information",
        "parameters": {
            "type": "object",
            "properties": {
                "detail_level": {"type": "string", "enum": ["summary", "verbose"], "description": "Level of detail"},
            },
            "required": ["detail_level"],
        },
    },
}

def log(tag: str, msg: str):
    print(f"[{tag}] {msg}", flush=True)

async def test_phase1_basic(client: httpx.AsyncClient) -> dict:
    log("PHASE 1", "Testing basic chat completion across all 7 models...")
    results = {}
    for m in MODELS:
        headers = {"Authorization": f"Bearer {m['key']}", "Content-Type": "application/json"}
        payload = {
            "model": m["model"],
            "messages": [{"role": "user", "content": "Respond with exactly the single word: OK"}],
            "max_tokens": 150,
        }
        t0 = time.time()
        try:
            resp = await client.post(f"{GATEWAY}/v1/chat/completions", headers=headers, json=payload, timeout=30)
            lat = round((time.time() - t0) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"] or ""
                log("PASS", f"{m['role']:<10} {m['model']:<28} {lat}ms -> {repr(content[:30])}")
                results[m["model"]] = True
            else:
                log("FAIL", f"{m['role']:<10} {m['model']:<28} HTTP {resp.status_code}: {resp.text[:100]}")
                results[m["model"]] = False
        except Exception as e:
            log("ERROR", f"{m['role']} {m['model']} Exception: {e}")
            results[m["model"]] = False
        await asyncio.sleep(0.5)
    return results

async def test_phase2_tools(client: httpx.AsyncClient) -> dict:
    log("PHASE 2", "Testing tool calling declaration across all 7 models...")
    results = {}
    for m in MODELS:
        headers = {"Authorization": f"Bearer {m['key']}", "Content-Type": "application/json"}
        payload = {
            "model": m["model"],
            "messages": [{"role": "user", "content": "Call the system_info tool with detail_level='summary' to inspect the machine."}],
            "tools": [SAMPLE_TOOL],
            "tool_choice": "auto",
            "max_tokens": 300,
        }
        t0 = time.time()
        try:
            resp = await client.post(f"{GATEWAY}/v1/chat/completions", headers=headers, json=payload, timeout=30)
            lat = round((time.time() - t0) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                msg = data["choices"][0]["message"]
                tcs = msg.get("tool_calls", [])
                if tcs:
                    fn = tcs[0]["function"]
                    sig = tcs[0].get("thought_signature") or tcs[0].get("thoughtSignature")
                    sig_status = "has-sig" if sig else "no-sig"
                    log("PASS", f"{m['role']:<10} {m['model']:<28} {lat}ms -> called {fn.get('name')}({fn.get('arguments')}) [{sig_status}]")
                    results[m["model"]] = True
                else:
                    log("FAIL", f"{m['role']:<10} {m['model']:<28} Did not call tool: {repr(msg.get('content')[:50])}")
                    results[m["model"]] = False
            else:
                log("FAIL", f"{m['role']:<10} {m['model']:<28} HTTP {resp.status_code}: {resp.text[:100]}")
                results[m["model"]] = False
        except Exception as e:
            log("ERROR", f"{m['role']} {m['model']} Exception: {e}")
            results[m["model"]] = False
        await asyncio.sleep(0.5)
    return results

async def test_phase3_multiturn(client: httpx.AsyncClient) -> dict:
    log("PHASE 3", "Testing multi-turn state & thought_signature persistence across all 7 models...")
    results = {}
    for m in MODELS:
        headers = {"Authorization": f"Bearer {m['key']}", "Content-Type": "application/json"}
        # Turn 1: Ask for tool call
        p1 = {
            "model": m["model"],
            "messages": [{"role": "user", "content": "Call the system_info tool with detail_level='summary' to inspect the machine."}],
            "tools": [SAMPLE_TOOL],
            "tool_choice": "required",
            "max_tokens": 500,
        }
        t0 = time.time()
        try:
            r1 = await client.post(f"{GATEWAY}/v1/chat/completions", headers=headers, json=p1, timeout=30)
            if r1.status_code != 200:
                log("FAIL", f"{m['model']} Turn 1 failed: HTTP {r1.status_code}")
                results[m["model"]] = False
                continue

            d1 = r1.json()
            asst_msg = d1["choices"][0]["message"]
            tcs = asst_msg.get("tool_calls", [])
            if not tcs:
                log("FAIL", f"{m['model']} Turn 1 did not return tool call")
                results[m["model"]] = False
                continue

            tc = tcs[0]
            call_id = tc["id"]
            fn_name = tc["function"]["name"]

            # Turn 2: Send tool result back (Hermes protocol)
            tool_msg = {
                "role": "tool",
                "tool_call_id": call_id,
                "name": fn_name,
                "content": json.dumps({"status": "healthy", "os": "Windows 11 x64", "cores": 16}),
            }

            p2 = {
                "model": m["model"],
                "messages": [
                    {"role": "user", "content": "Call the system_info tool with detail_level='summary'"},
                    asst_msg,
                    tool_msg,
                ],
                "tools": [SAMPLE_TOOL],
                "max_tokens": 500,
            }

            r2 = await client.post(f"{GATEWAY}/v1/chat/completions", headers=headers, json=p2, timeout=30)
            lat = round((time.time() - t0) * 1000)
            if r2.status_code == 200:
                d2 = r2.json()
                final_text = d2["choices"][0]["message"]["content"] or ""
                log("PASS", f"{m['role']:<10} {m['model']:<28} {lat}ms -> Turn 2 synthesized: {repr(final_text[:40])}")
                results[m["model"]] = True
            else:
                log("FAIL", f"{m['role']:<10} {m['model']:<28} Turn 2 failed: HTTP {r2.status_code}: {r2.text[:120]}")
                results[m["model"]] = False
        except Exception as e:
            log("ERROR", f"{m['role']} {m['model']} Exception: {e}")
            results[m["model"]] = False
        await asyncio.sleep(0.5)
    return results

async def test_phase4_streaming(client: httpx.AsyncClient) -> dict:
    log("PHASE 4", "Testing streaming SSE response integrity across all 7 models...")
    results = {}
    for m in MODELS:
        headers = {"Authorization": f"Bearer {m['key']}", "Content-Type": "application/json"}
        payload = {
            "model": m["model"],
            "messages": [{"role": "user", "content": "Count from 1 to 5 separated by spaces."}],
            "stream": True,
            "max_tokens": 200,
        }
        t0 = time.time()
        collected = []
        try:
            async with client.stream("POST", f"{GATEWAY}/v1/chat/completions", headers=headers, json=payload, timeout=30) as resp:
                if resp.status_code == 200:
                    async for line in resp.aiter_lines():
                        if line.startswith("data:"):
                            chunk_raw = line[5:].strip()
                            if chunk_raw == "[DONE]":
                                break
                            try:
                                chunk = json.loads(chunk_raw)
                                delta = chunk["choices"][0]["delta"].get("content", "")
                                if delta:
                                    collected.append(delta)
                            except Exception:
                                pass
                    full_text = "".join(collected).strip()
                    lat = round((time.time() - t0) * 1000)
                    log("PASS", f"{m['role']:<10} {m['model']:<28} {lat}ms ({len(collected)} chunks) -> {repr(full_text[:35])}")
                    results[m["model"]] = bool(full_text)
                else:
                    err_body = await resp.aread()
                    log("FAIL", f"{m['role']:<10} {m['model']:<28} HTTP {resp.status_code}: {err_body.decode()[:100]}")
                    results[m["model"]] = False
        except Exception as e:
            log("ERROR", f"{m['role']} {m['model']} Exception: {e}")
            results[m["model"]] = False
        await asyncio.sleep(0.5)
    return results

def test_phase5_hermes_cli() -> dict:
    log("PHASE 5", "Testing live Hermes CLI profile executions...")
    profiles_to_test = [
        ("Default (Coding-1)", []),
        ("architect-worker", ["--profile", "architect-worker"]),
        ("code-runner", ["--profile", "code-runner"]),
        ("dev-dedicated", ["--profile", "dev-dedicated"]),
    ]
    results = {}
    for label, args in profiles_to_test:
        cmd = ["hermes", "-z", "Reply with ONLINE"] + args
        t0 = time.time()
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            lat = round((time.time() - t0) * 1000)
            out = res.stdout.strip().replace("\n", " ")
            if res.returncode == 0 and out:
                log("PASS", f"{label:<25} {lat}ms -> {repr(out[:40])}")
                results[label] = True
            else:
                err = res.stderr.strip()[:100] or out[:100]
                log("FAIL", f"{label:<25} code={res.returncode}: {err}")
                results[label] = False
        except Exception as e:
            log("ERROR", f"{label:<25} Exception: {e}")
            results[label] = False
    return results

async def main():
    print("=" * 75)
    print("  ANTIGRAVITY GATEWAY -- DEDICATED HERMES AGENT VERIFICATION")
    print(f"  Time:    {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Gateway: {GATEWAY}")
    print("=" * 75)

    async with httpx.AsyncClient() as client:
        # Check health
        health = await client.get(f"{GATEWAY}/health", timeout=5)
        log("GATEWAY", f"Status {health.status_code}: {health.text}")

        r1 = await test_phase1_basic(client)
        r2 = await test_phase2_tools(client)
        r3 = await test_phase3_multiturn(client)
        r4 = await test_phase4_streaming(client)

    r5 = test_phase5_hermes_cli()

    print("\n" + "=" * 75)
    print("  FINAL SCORECARD")
    print("=" * 75)
    all_phases = [
        ("Phase 1: Basic Completions", r1),
        ("Phase 2: Tool Declarations", r2),
        ("Phase 3: Multi-turn / State", r3),
        ("Phase 4: Streaming SSE", r4),
        ("Phase 5: Hermes CLI Profiles", r5),
    ]
    total_passed = 0
    total_tests = 0
    for name, r in all_phases:
        p_count = sum(1 for v in r.values() if v)
        t_count = len(r)
        total_passed += p_count
        total_tests += t_count
        status = "ALL PASS" if p_count == t_count else f"{p_count}/{t_count} PASS"
        print(f"  {name:<32} {status}")

    print("-" * 75)
    print(f"  OVERALL RESULT: {total_passed}/{total_tests} tests passed")
    print("=" * 75)

    return 0 if total_passed == total_tests else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
