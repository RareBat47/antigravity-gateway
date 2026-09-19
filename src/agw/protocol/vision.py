"""Multimodal image handling and vision format conversion."""

import base64
import mimetypes
from typing import Any, Dict, List, Optional
import httpx


async def process_image_url(url: str) -> Optional[Dict[str, Any]]:
    """Convert an image URL (data URL or http/https) into inlineData part."""
    if not url:
        return None

    # Handle data:image/png;base64,...
    if url.startswith("data:"):
        header, _, data = url.partition(",")
        mime_type = "image/jpeg"
        if ";" in header:
            mime_part = header.split(";")[0]
            if ":" in mime_part:
                mime_type = mime_part.split(":")[1]
        return {
            "inlineData": {
                "mimeType": mime_type,
                "data": data,
            }
        }

    # Handle HTTP/HTTPS remote URL
    if url.startswith("http://") or url.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
                    b64_data = base64.b64encode(resp.content).decode("utf-8")
                    return {
                        "inlineData": {
                            "mimeType": content_type,
                            "data": b64_data,
                        }
                    }
        except Exception:
            pass

    return None
