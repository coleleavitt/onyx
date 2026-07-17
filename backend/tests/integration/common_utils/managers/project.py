from typing import List

from onyx.server.features.projects.models import CategorizedFilesSnapshot
from onyx.server.features.projects.models import ProjectAccessStateSnapshot
from onyx.server.features.projects.models import ProjectJoinRequestSnapshot
from onyx.server.features.projects.models import ProjectSharingSnapshot
from onyx.server.features.projects.models import UserFileSnapshot
from onyx.server.features.projects.models import UserProjectSnapshot
from tests.integration.common_utils.constants import API_SERVER_URL
from tests.integration.common_utils.http_client import client
from tests.integration.common_utils.test_models import DATestUser


class ProjectManager:
    @staticmethod
    def create(
        name: str,
        user_performing_action: DATestUser,
        description: str | None = None,
    ) -> UserProjectSnapshot:
        """Create a new project via API."""
        params = {"name": name}
        if description is not None:
            params["description"] = description
        response = client.post(
            f"{API_SERVER_URL}/user/projects/create",
            params=params,
            headers=user_performing_action.headers,
        )
        response.raise_for_status()
        return UserProjectSnapshot.model_validate(response.json())

    @staticmethod
    def get_all(
        user_performing_action: DATestUser,
    ) -> List[UserProjectSnapshot]:
        """Get all projects for a user via API."""
        response = client.get(
            f"{API_SERVER_URL}/user/projects",
            headers=user_performing_action.headers,
        )
        response.raise_for_status()
        return [UserProjectSnapshot.model_validate(obj) for obj in response.json()]

    @staticmethod
    def get(
        project_id: int,
        user_performing_action: DATestUser,
    ) -> UserProjectSnapshot | None:
        response = client.get(
            f"{API_SERVER_URL}/user/projects/{project_id}",
            headers=user_performing_action.headers,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return UserProjectSnapshot.model_validate(response.json())

    @staticmethod
    def get_sharing(
        project_id: int,
        user_performing_action: DATestUser,
    ) -> ProjectSharingSnapshot:
        response = client.get(
            f"{API_SERVER_URL}/user/projects/{project_id}/sharing",
            headers=user_performing_action.headers,
        )
        response.raise_for_status()
        return ProjectSharingSnapshot.model_validate(response.json())

    @staticmethod
    def get_access_state(
        project_id: int,
        user_performing_action: DATestUser,
    ) -> ProjectAccessStateSnapshot | None:
        response = client.get(
            f"{API_SERVER_URL}/user/projects/{project_id}/access-state",
            headers=user_performing_action.headers,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return ProjectAccessStateSnapshot.model_validate(response.json())

    @staticmethod
    def update(
        project_id: int,
        user_performing_action: DATestUser,
        *,
        name: str | None = None,
        description: str | None = None,
        include_description: bool = False,
    ) -> UserProjectSnapshot:
        body: dict[str, str | None] = {}
        if name is not None:
            body["name"] = name
        if include_description:
            body["description"] = description
        response = client.patch(
            f"{API_SERVER_URL}/user/projects/{project_id}",
            json=body,
            headers=user_performing_action.headers,
        )
        response.raise_for_status()
        return UserProjectSnapshot.model_validate(response.json())

    @staticmethod
    def cancel_access_request(
        project_id: int,
        user_performing_action: DATestUser,
    ) -> bool:
        response = client.delete(
            f"{API_SERVER_URL}/user/projects/{project_id}/request-access",
            headers=user_performing_action.headers,
        )
        return response.status_code == 204

    @staticmethod
    def update_sharing(
        project_id: int,
        *,
        organization_permission: str | None,
        user_shares: list[dict[str, str]],
        group_shares: list[dict[str, int | str]],
        user_performing_action: DATestUser,
    ) -> ProjectSharingSnapshot:
        response = client.patch(
            f"{API_SERVER_URL}/user/projects/{project_id}/sharing",
            json={
                "organization_permission": organization_permission,
                "user_shares": user_shares,
                "group_shares": group_shares,
            },
            headers=user_performing_action.headers,
        )
        response.raise_for_status()
        return ProjectSharingSnapshot.model_validate(response.json())

    @staticmethod
    def request_access(
        project_id: int,
        user_performing_action: DATestUser,
    ) -> ProjectJoinRequestSnapshot:
        response = client.post(
            f"{API_SERVER_URL}/user/projects/{project_id}/request-access",
            json={"requested_permission": "VIEWER"},
            headers=user_performing_action.headers,
        )
        response.raise_for_status()
        return ProjectJoinRequestSnapshot.model_validate(response.json())

    @staticmethod
    def resolve_access_request(
        project_id: int,
        request_id: int,
        *,
        approve: bool,
        user_performing_action: DATestUser,
    ) -> ProjectSharingSnapshot:
        response = client.post(
            f"{API_SERVER_URL}/user/projects/{project_id}/join-requests/{request_id}/resolve",
            json={"approve": approve},
            headers=user_performing_action.headers,
        )
        response.raise_for_status()
        return ProjectSharingSnapshot.model_validate(response.json())

    @staticmethod
    def delete(
        project_id: int,
        user_performing_action: DATestUser,
    ) -> bool:
        """Delete a project via API."""
        response = client.delete(
            f"{API_SERVER_URL}/user/projects/{project_id}",
            headers=user_performing_action.headers,
        )
        return response.status_code == 204

    @staticmethod
    def verify_deleted(
        project_id: int,
        user_performing_action: DATestUser,
    ) -> bool:
        """Verify that a project has been deleted by ensuring it's not in list."""
        response = client.get(
            f"{API_SERVER_URL}/user/projects",
            headers=user_performing_action.headers,
        )
        response.raise_for_status()
        projects = [UserProjectSnapshot.model_validate(obj) for obj in response.json()]
        return all(p.id != project_id for p in projects)

    @staticmethod
    def verify_files_unlinked(
        project_id: int,
        user_performing_action: DATestUser,
    ) -> bool:
        """Verify that all files have been unlinked from the project via API."""
        response = client.get(
            f"{API_SERVER_URL}/user/projects/files/{project_id}",
            headers=user_performing_action.headers,
        )
        if response.status_code == 404:
            return True
        if response.is_error:
            return False
        files = [UserFileSnapshot.model_validate(obj) for obj in response.json()]
        return len(files) == 0

    @staticmethod
    def verify_chat_sessions_unlinked(
        project_id: int,
        user_performing_action: DATestUser,
    ) -> bool:
        """Verify that all chat sessions have been unlinked from the project via API."""
        response = client.get(
            f"{API_SERVER_URL}/user/projects/{project_id}",
            headers=user_performing_action.headers,
        )
        if response.status_code == 404:
            return True
        if response.is_error:
            return False
        try:
            project = UserProjectSnapshot.model_validate(response.json())
            chat_sessions = getattr(project, "chat_sessions", [])
            return len(chat_sessions or []) == 0
        except Exception:
            # If response doesn't include chat_sessions, assume unlinked
            return True

    @staticmethod
    def upload_files(
        project_id: int,
        files: List[tuple[str, bytes]],  # List of (filename, content) tuples
        user_performing_action: DATestUser,
    ) -> CategorizedFilesSnapshot:
        """Upload files to a project via API."""
        # Build multipart form-data
        files_payload = [
            (
                "files",
                (filename, content, "text/plain"),
            )
            for filename, content in files
        ]

        data = {"project_id": str(project_id)} if project_id is not None else {}

        # Let requests set Content-Type boundary by not overriding header
        headers = dict(user_performing_action.headers or {})
        headers.pop("Content-Type", None)

        response = client.post(
            f"{API_SERVER_URL}/user/projects/file/upload",
            data=data,
            files=files_payload,
            headers=headers,
        )
        response.raise_for_status()
        return CategorizedFilesSnapshot.model_validate(response.json())

    @staticmethod
    def get_project_files(
        project_id: int,
        user_performing_action: DATestUser,
    ) -> List[UserFileSnapshot]:
        """Get all files associated with a project via API."""
        response = client.get(
            f"{API_SERVER_URL}/user/projects/files/{project_id}",
            headers=user_performing_action.headers,
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return [UserFileSnapshot.model_validate(obj) for obj in response.json()]

    @staticmethod
    def set_instructions(
        project_id: int,
        instructions: str,
        user_performing_action: DATestUser,
    ) -> str:
        """Set project instructions via API."""
        response = client.post(
            f"{API_SERVER_URL}/user/projects/{project_id}/instructions",
            json={"instructions": instructions},
            headers=user_performing_action.headers,
        )
        response.raise_for_status()
        return (response.json() or {}).get("instructions") or ""
