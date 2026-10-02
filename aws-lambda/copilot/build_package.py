from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import faiss
import numpy as np


PACKAGE_DIR = Path(__file__).resolve().parent / "build" / "package"
ZIP_PATH = PACKAGE_DIR.parent / "copilot-lambda.zip"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

PACKAGE_FILES = (
    "backend/app/__init__.py",
    "backend/app/config.py",
    "backend/app/copilot_main.py",
    "backend/app/copilot_service.py",
    "backend/app/models.py",
    "copilot/__init__.py",
    "copilot/rag.py",
    "copilot/lambda_rag.py",
    "copilot/llm.py",
    "copilot/documents/demo_migration_knowledge.pdf",
    "copilot/vectorstore/chunks.txt",
)


def build() -> None:
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True)

    index_path = REPOSITORY_ROOT / "copilot/vectorstore/migration.index"
    index = faiss.read_index(str(index_path))
    if not isinstance(index, faiss.IndexFlatL2):
        raise ValueError("Expected the existing IndexFlatL2 Copilot vectorstore.")
    if index.ntotal == 0:
        raise ValueError("The existing Copilot vectorstore is empty.")

    vectors = np.vstack([index.reconstruct(vector_id) for vector_id in range(index.ntotal)])
    vectors = np.asarray(vectors, dtype=np.float32)
    vectorstore_dir = PACKAGE_DIR / "copilot/vectorstore"
    vectorstore_dir.mkdir(parents=True, exist_ok=True)
    np.save(vectorstore_dir / "migration_vectors.npy", vectors, allow_pickle=False)

    for relative_path in PACKAGE_FILES:
        source = REPOSITORY_ROOT / relative_path
        if not source.is_file():
            raise FileNotFoundError(f"Required Copilot package file is missing: {relative_path}")
        destination = PACKAGE_DIR / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--only-binary=:all:",
            "--implementation",
            "cp",
            "--python-version",
            "3.12",
            "--abi",
            "cp312",
            "--platform",
            "manylinux_2_28_x86_64",
            "--platform",
            "manylinux_2_17_x86_64",
            "--target",
            str(PACKAGE_DIR),
            "-r",
            str(Path(__file__).with_name("requirements.txt")),
        ],
        check=True,
    )

    for cache_dir in list(PACKAGE_DIR.rglob("__pycache__")):
        shutil.rmtree(cache_dir)
    for bytecode_file in PACKAGE_DIR.rglob("*.pyc"):
        bytecode_file.unlink()

    with ZipFile(ZIP_PATH, "w", compression=ZIP_DEFLATED, compresslevel=6) as package_zip:
        for path in PACKAGE_DIR.rglob("*"):
            if path.is_file():
                package_zip.write(path, path.relative_to(PACKAGE_DIR).as_posix())

    package_size = sum(path.stat().st_size for path in PACKAGE_DIR.rglob("*") if path.is_file())
    print(f"Lambda package prepared at {PACKAGE_DIR}")
    print(f"Vector shape: {vectors.shape}; dtype: {vectors.dtype}; bytes: {vectors.nbytes}")
    print(f"Uncompressed package size: {package_size:,} bytes")
    print(f"ZIP package size: {ZIP_PATH.stat().st_size:,} bytes")


if __name__ == "__main__":
    build()