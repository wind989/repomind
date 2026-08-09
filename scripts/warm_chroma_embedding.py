"""Download and validate Chroma's default local embedding model once.

Run this before the first real knowledge-base indexing request when the local
network is slow:

    .venv\Scripts\python.exe scripts\warm_chroma_embedding.py
"""

from __future__ import annotations

import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2, _verify_sha256


PART_COUNT = 4
CHUNK_SIZE = 1024 * 1024


def get_remote_size() -> int:
    request = Request(
        ONNXMiniLM_L6_V2.MODEL_DOWNLOAD_URL,
        headers={"Range": "bytes=0-0", "User-Agent": "RepoMind/0.1"},
    )
    with urlopen(request, timeout=30) as response:
        content_range = response.headers.get("Content-Range")
        if not content_range:
            raise RuntimeError("模型源未返回文件总大小")
        return int(content_range.rsplit("/", 1)[-1])


def download_part(part_number: int, start: int, end: int, part_path: Path) -> None:
    expected_size = end - start + 1
    for attempt in range(1, 11):
        downloaded = part_path.stat().st_size if part_path.exists() else 0
        if downloaded == expected_size:
            return
        if downloaded > expected_size:
            part_path.unlink()
            downloaded = 0
        request = Request(
            ONNXMiniLM_L6_V2.MODEL_DOWNLOAD_URL,
            headers={
                "Range": f"bytes={start + downloaded}-{end}",
                "User-Agent": "RepoMind/0.1",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                if response.status != 206:
                    raise RuntimeError(f"模型源未按范围返回第 {part_number} 段")
                with part_path.open("ab") as file:
                    while data := response.read(CHUNK_SIZE):
                        file.write(data)
                        print(
                            f"Downloading Chroma model part {part_number}: "
                            f"{file.tell()}/{expected_size} bytes",
                            flush=True,
                        )
            if part_path.stat().st_size == expected_size:
                return
            raise RuntimeError(f"第 {part_number} 段长度不完整")
        except Exception as exc:
            if attempt == 10:
                raise RuntimeError(f"第 {part_number} 段下载失败") from exc
            print(f"Part {part_number} attempt {attempt} failed, retrying: {exc}", flush=True)
            time.sleep(attempt)


def download_archive_with_urllib() -> None:
    """Use resumable ranged downloads when Chroma's bundled downloader is unstable."""
    model_dir = Path(ONNXMiniLM_L6_V2.DOWNLOAD_PATH)
    archive_path = model_dir / ONNXMiniLM_L6_V2.ARCHIVE_FILENAME
    sequential_temporary_path = archive_path.with_suffix(archive_path.suffix + ".download")
    combined_temporary_path = archive_path.with_suffix(archive_path.suffix + ".parallel.download")
    model_dir.mkdir(parents=True, exist_ok=True)

    if archive_path.exists() and _verify_sha256(str(archive_path), ONNXMiniLM_L6_V2._MODEL_SHA256):
        return

    total_size = get_remote_size()
    part_size = (total_size + PART_COUNT - 1) // PART_COUNT
    parts = [
        (
            number,
            (number - 1) * part_size,
            min(number * part_size, total_size) - 1,
            model_dir / f"{archive_path.name}.part{number}",
        )
        for number in range(1, PART_COUNT + 1)
    ]
    with ThreadPoolExecutor(max_workers=PART_COUNT) as executor:
        futures = [
            executor.submit(download_part, number, start, end, part_path)
            for number, start, end, part_path in parts
        ]
        for future in futures:
            future.result()

    with combined_temporary_path.open("wb") as destination:
        for _, _, _, part_path in parts:
            with part_path.open("rb") as source:
                shutil.copyfileobj(source, destination, length=CHUNK_SIZE)
    if not _verify_sha256(str(combined_temporary_path), ONNXMiniLM_L6_V2._MODEL_SHA256):
        raise RuntimeError("下载文件的 SHA-256 校验失败")
    os.replace(combined_temporary_path, archive_path)
    sequential_temporary_path.unlink(missing_ok=True)
    for _, _, _, part_path in parts:
        part_path.unlink(missing_ok=True)


def main() -> None:
    download_archive_with_urllib()
    embedding_function = DefaultEmbeddingFunction()
    vectors = embedding_function(["RepoMind embedding warm-up"])
    if len(vectors) == 0 or len(vectors[0]) == 0:
        raise RuntimeError("Chroma 未返回嵌入向量")
    print(f"Chroma embedding ready: dimensions={len(vectors[0])}")


if __name__ == "__main__":
    main()
