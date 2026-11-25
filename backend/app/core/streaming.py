import os
from pathlib import Path
from typing import Generator
from fastapi import Request, HTTPException, status
from fastapi.responses import StreamingResponse

def stream_file_with_ranges(
    request: Request,
    file_path: str,
    content_type: str = "video/mp4"
) -> StreamingResponse:
    """
    Return a StreamingResponse with support for HTTP 206 Partial Content range requests,
    allowing HTML5 video players to seek smoothly without buffering the entire file.
    """
    p = Path(file_path).resolve()
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Requested media file not found")

    file_size = p.stat().st_size
    range_header = request.headers.get("Range")

    if not range_header:
        # Full file stream
        def iterfile() -> Generator[bytes, None, None]:
            with open(p, mode="rb") as f:
                while chunk := f.read(1024 * 512):
                    yield chunk

        return StreamingResponse(
            iterfile(),
            status_code=status.HTTP_200_OK,
            headers={
                "Content-Length": str(file_size),
                "Content-Type": content_type,
                "Accept-Ranges": "bytes"
            }
        )

    # Parse Range: bytes=start-end
    try:
        range_spec = range_header.replace("bytes=", "").strip()
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1

        if start >= file_size or end >= file_size or start > end:
            raise HTTPException(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                detail="Invalid byte range requested",
                headers={"Content-Range": f"bytes */{file_size}"}
            )

        content_length = end - start + 1

        def iter_range() -> Generator[bytes, None, None]:
            with open(p, mode="rb") as f:
                f.seek(start)
                bytes_left = content_length
                while bytes_left > 0:
                    read_size = min(1024 * 512, bytes_left)
                    chunk = f.read(read_size)
                    if not chunk:
                        break
                    bytes_left -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
                "Content-Type": content_type,
                "Accept-Ranges": "bytes"
            }
        )
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Malformed Range header"
        )
