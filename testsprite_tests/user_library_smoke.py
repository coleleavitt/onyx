#!/usr/bin/env python3
"""Live User Library file/directory lifecycle through the frontend proxy.

Covers the previously untested Craft User Library tree/upload behaviors
(build router mounts under /build):
- POST /api/build/user-library/upload (multipart, raw binary file)
- GET  /api/build/user-library/tree
- POST /api/build/user-library/directories
- DELETE /api/build/user-library/files/{document_id}
with file + directory cleanup.

The document_id returned by upload/mkdir is the stable identifier used in the
tree, so membership is asserted by id (the tree's `path` carries a
`user_library/` prefix the upload/mkdir responses do not).
"""
from __future__ import annotations

import os
import uuid

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
USER_EMAIL = os.environ["EMAIL"]
USER_PASSWORD = os.environ["PASSWORD"]


def login(email: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        timeout=20,
    )
    assert response.status_code == 204, response.text
    return session


def tree_ids(session: requests.Session) -> set[str]:
    response = session.get(
        f"{BASE_URL}/api/build/user-library/tree",
        timeout=30,
    )
    assert response.ok, response.text
    return {entry["id"] for entry in response.json()}


def main() -> None:
    session = login(USER_EMAIL, USER_PASSWORD)

    suffix = uuid.uuid4().hex[:8]
    file_name = f"userlib_smoke_{suffix}.txt"
    dir_name = f"userlib_smoke_dir_{suffix}"
    file_body = b"user library smoke payload"

    upload_response = session.post(
        f"{BASE_URL}/api/build/user-library/upload",
        files={"files": (file_name, file_body, "text/plain")},
        data={"path": "/"},
        timeout=60,
    )
    assert upload_response.ok, upload_response.text
    upload_payload = upload_response.json()
    entry = upload_payload["entries"][0]
    file_id = entry["id"]

    # Arm cleanup the moment the file exists server-side. The value assertions
    # below (the endpoint-regression case this smoke guards) run inside the try
    # so a failing one can't orphan the just-uploaded file.
    dir_id: str | None = None
    try:
        assert upload_payload["total_uploaded"] == 1, upload_payload
        assert upload_payload["total_size_bytes"] == len(file_body), upload_payload
        assert entry["name"] == file_name, entry
        assert entry["is_directory"] is False, entry
        assert entry["file_size"] == len(file_body), entry

        # Uploaded file must appear in the tree.
        after_upload = tree_ids(session)
        assert file_id in after_upload, (file_id, after_upload)

        # Create a directory; it must appear in the tree.
        mkdir_response = session.post(
            f"{BASE_URL}/api/build/user-library/directories",
            json={"name": dir_name, "parent_path": "/"},
            timeout=30,
        )
        assert mkdir_response.ok, mkdir_response.text
        dir_payload = mkdir_response.json()
        dir_id = dir_payload["id"]
        assert dir_payload["is_directory"] is True, dir_payload
        assert dir_payload["name"] == dir_name, dir_payload

        after_mkdir = tree_ids(session)
        assert dir_id in after_mkdir, (dir_id, after_mkdir)
        assert file_id in after_mkdir, (file_id, after_mkdir)
    finally:
        # Attempt every delete regardless of which one fails, so a broken
        # delete for one entity can't leak the other. Assertion of success is
        # deferred until after all cleanup has run.
        cleanup_errors: list[str] = []
        delete_file_response = session.delete(
            f"{BASE_URL}/api/build/user-library/files/{file_id}",
            timeout=30,
        )
        if not delete_file_response.ok:
            cleanup_errors.append(f"file delete failed: {delete_file_response.text}")
        if dir_id is not None:
            delete_dir_response = session.delete(
                f"{BASE_URL}/api/build/user-library/files/{dir_id}",
                timeout=30,
            )
            if not delete_dir_response.ok:
                cleanup_errors.append(f"dir delete failed: {delete_dir_response.text}")
        assert not cleanup_errors, cleanup_errors

    # After deletion neither the file nor the directory should remain.
    final_ids = tree_ids(session)
    assert file_id not in final_ids, (file_id, final_ids)
    assert dir_id not in final_ids, (dir_id, final_ids)

    print("user library smoke passed")


if __name__ == "__main__":
    main()
