import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.storage import (
    InvalidStoragePath,
    build_upload_filename,
    resolve_backup_path,
    resolve_upload_path,
)
from app.main import app


@pytest.mark.parametrize(
    "bad_name",
    [
        "",
        ".",
        "..",
        "../secret.xlsx",
        "..\\secret.xlsx",
        "sub/dir.xlsx",
        "sub\\dir.xlsx",
        "/etc/passwd",
        "C:\\Windows\\win.ini",
        "../../tests/sample_data/sample_bank.xlsx",
    ],
)
def test_resolve_upload_path_rejects_traversal(bad_name):
    with pytest.raises(InvalidStoragePath):
        resolve_upload_path(bad_name)


def test_resolve_upload_path_accepts_plain_file_inside_upload_dir():
    name = f"{uuid.uuid4()}_report.xlsx"
    resolved = resolve_upload_path(name)
    assert os.path.dirname(resolved) == os.path.realpath(settings.UPLOAD_DIR)
    assert os.path.basename(resolved) == name


@pytest.mark.parametrize("bad_name", ["../x.json", "..\\x.json", "a/b.json", ""])
def test_resolve_backup_path_rejects_traversal(bad_name):
    with pytest.raises(InvalidStoragePath):
        resolve_backup_path(bad_name)


@pytest.mark.parametrize(
    "original, expected_suffix",
    [
        ("kassa.xlsx", "_kassa.xlsx"),
        ("../../evil.xlsx", "_evil.xlsx"),
        ("..\\..\\evil.csv", "_evil.csv"),
        ("C:\\Users\\x\\data.pdf", "_data.pdf"),
    ],
)
def test_build_upload_filename_strips_directories(original, expected_suffix):
    name = build_upload_filename(original)
    assert name.endswith(expected_suffix)
    assert "/" not in name and "\\" not in name
    assert name == os.path.basename(name)


@pytest.mark.asyncio
async def test_preview_mapping_rejects_path_traversal():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/documents/preview-mapping",
            data={"file_id": "../../tests/sample_data/sample_bank.xlsx"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_commit_rejects_path_traversal():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/documents/commit",
            json={
                "file_id": "../../tests/sample_data/sample_bank.xlsx",
                "organization_id": str(uuid.uuid4()),
                "format_type": "DIDOX_EHF",
            },
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_backup_verify_rejects_path_traversal():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/backup/..%5C..%5Csecret.json/verify",
            headers={"X-User-Role": "CHIEF_ACCOUNTANT"},
        )
    assert resp.status_code in (400, 404)
