from typing import List

import pytest

from onyx.db.engine.sql_engine import get_session_with_current_tenant
from onyx.db.models import UserFile
from onyx.server.features.projects.models import UserProjectSnapshot
from tests.integration.common_utils.managers.project import ProjectManager
from tests.integration.common_utils.reset import reset_all
from tests.integration.common_utils.test_models import DATestLLMProvider
from tests.integration.common_utils.test_models import DATestUser


@pytest.fixture(scope="module", autouse=True)
def reset_for_module() -> None:
    """Reset all data once before running any tests in this module."""
    reset_all()


def test_projects_flow(
    reset_for_module: None,  # noqa: ARG001
    basic_user: DATestUser,
    llm_provider: DATestLLMProvider,  # noqa: ARG001
) -> None:
    """End-to-end project flow covering creation, listing, files, instructions, deletion, and edge cases."""
    # Case 1: Project creation and listing
    ProjectManager.create(
        name="Test Project 1",
        user_performing_action=basic_user,
    )
    ProjectManager.create(
        name="Test Project 2",
        user_performing_action=basic_user,
    )

    projects = ProjectManager.get_all(user_performing_action=basic_user)
    assert len(projects) >= 2
    project_names = {p.name for p in projects}
    assert "Test Project 1" in project_names
    assert "Test Project 2" in project_names
    assert all(str(p.user_id) == basic_user.id for p in projects)

    # Case 2: File upload and management
    file_project = ProjectManager.create(
        name="File Test Project",
        user_performing_action=basic_user,
    )
    test_files = [
        ("test1.txt", b"This is test file 1 content"),
        ("test2.txt", b"This is test file 2 content"),
    ]
    upload_result = ProjectManager.upload_files(
        project_id=file_project.id,
        files=test_files,
        user_performing_action=basic_user,
    )
    assert len(upload_result.user_files) == 2
    assert len(upload_result.rejected_files) == 0
    project_files = ProjectManager.get_project_files(
        project_id=file_project.id,
        user_performing_action=basic_user,
    )
    assert len(project_files) == 2
    file_names = {f.name for f in project_files}
    assert "test1.txt" in file_names
    assert "test2.txt" in file_names

    # Case 3: Instructions set and update
    instructions_project = ProjectManager.create(
        name="Instructions Test Project",
        user_performing_action=basic_user,
    )
    instructions = "These are test project instructions"
    result = ProjectManager.set_instructions(
        project_id=instructions_project.id,
        instructions=instructions,
        user_performing_action=basic_user,
    )
    assert result == instructions
    new_instructions = "These are updated test project instructions"
    result = ProjectManager.set_instructions(
        project_id=instructions_project.id,
        instructions=new_instructions,
        user_performing_action=basic_user,
    )
    assert result == new_instructions

    # Case 4: Deletion with files (unlink but do not delete files)
    delete_file_project = ProjectManager.create(
        name="Deletion Test Project",
        user_performing_action=basic_user,
    )
    del_test_files = [
        ("delete_test1.txt", b"This is test file 1 content"),
        ("delete_test2.txt", b"This is test file 2 content"),
    ]
    ProjectManager.upload_files(
        project_id=delete_file_project.id,
        files=del_test_files,
        user_performing_action=basic_user,
    )
    del_project_files = ProjectManager.get_project_files(
        project_id=delete_file_project.id,
        user_performing_action=basic_user,
    )
    assert len(del_project_files) == 2
    deletion_success = ProjectManager.delete(
        project_id=delete_file_project.id,
        user_performing_action=basic_user,
    )
    assert deletion_success
    assert ProjectManager.verify_deleted(
        project_id=delete_file_project.id,
        user_performing_action=basic_user,
    )
    assert ProjectManager.verify_files_unlinked(
        project_id=delete_file_project.id,
        user_performing_action=basic_user,
    )
    with get_session_with_current_tenant() as db_session:
        file_ids = [f.id for f in del_project_files]
        remaining_files = (
            db_session.query(UserFile).filter(UserFile.id.in_(file_ids)).all()
        )
        assert len(remaining_files) == 2

    # Case 5: Deletion with chat sessions unlinked
    chat_project = ProjectManager.create(
        name="Chat Session Test Project",
        user_performing_action=basic_user,
    )
    deletion_success = ProjectManager.delete(
        project_id=chat_project.id,
        user_performing_action=basic_user,
    )
    assert deletion_success
    assert ProjectManager.verify_chat_sessions_unlinked(
        project_id=chat_project.id,
        user_performing_action=basic_user,
    )

    # Case 6: Multiple project operations
    projects_group: List[UserProjectSnapshot] = []
    for i in range(3):
        proj = ProjectManager.create(
            name=f"Multi-op Project {i}",
            user_performing_action=basic_user,
        )
        projects_group.append(proj)

    for i, proj in enumerate(projects_group):
        tfiles = [
            (f"multi_test{i}_1.txt", b"This is test file 1 content"),
            (f"multi_test{i}_2.txt", b"This is test file 2 content"),
        ]
        ProjectManager.upload_files(
            project_id=proj.id,
            files=tfiles,
            user_performing_action=basic_user,
        )

    for i, proj in enumerate(projects_group):
        instr = f"Instructions for project {i}"
        res = ProjectManager.set_instructions(
            project_id=proj.id,
            instructions=instr,
            user_performing_action=basic_user,
        )
        assert res == instr

    for proj in projects_group:
        proj_files = ProjectManager.get_project_files(
            project_id=proj.id,
            user_performing_action=basic_user,
        )
        assert len(proj_files) == 2
        deletion_success = ProjectManager.delete(
            project_id=proj.id,
            user_performing_action=basic_user,
        )
        assert deletion_success
        assert ProjectManager.verify_deleted(
            project_id=proj.id,
            user_performing_action=basic_user,
        )
        assert ProjectManager.verify_files_unlinked(
            project_id=proj.id,
            user_performing_action=basic_user,
        )
        with get_session_with_current_tenant() as db_session:
            file_ids = [f.id for f in proj_files]
            remaining_files = (
                db_session.query(UserFile).filter(UserFile.id.in_(file_ids)).all()
            )
            assert len(remaining_files) == 2

    # Case 7: Edge cases
    with pytest.raises(Exception):
        ProjectManager.create(
            name="",
            user_performing_action=basic_user,
        )

    non_existent_id = 99999
    deletion_success = ProjectManager.delete(
        project_id=non_existent_id,
        user_performing_action=basic_user,
    )
    assert not deletion_success

    with pytest.raises(Exception):
        ProjectManager.set_instructions(
            project_id=non_existent_id,
            instructions="Test instructions",
            user_performing_action=basic_user,
        )

    with pytest.raises(Exception):
        ProjectManager.upload_files(
            project_id=non_existent_id,
            files=[("test.txt", b"content")],
            user_performing_action=basic_user,
        )

    long_name = "a" * 1000
    with pytest.raises(Exception):
        ProjectManager.create(
            name=long_name,
            user_performing_action=basic_user,
        )

    long_instr_project = ProjectManager.create(
        name="Long Instructions Test",
        user_performing_action=basic_user,
    )
    long_instructions = "a" * 10000
    result = ProjectManager.set_instructions(
        project_id=long_instr_project.id,
        instructions=long_instructions,
        user_performing_action=basic_user,
    )
    assert result == long_instructions


def test_project_metadata_and_request_access_state(
    basic_user: DATestUser,
    admin_user: DATestUser,
) -> None:
    project = ProjectManager.create(
        name="  Metadata Project  ",
        description="  Shared research space  ",
        user_performing_action=basic_user,
    )
    assert project.name == "Metadata Project"
    assert project.description == "Shared research space"

    renamed = ProjectManager.update(
        project.id,
        basic_user,
        name="Renamed Metadata Project",
    )
    assert renamed.name == "Renamed Metadata Project"
    assert renamed.description == "Shared research space"

    cleared = ProjectManager.update(
        project.id,
        basic_user,
        description="   ",
        include_description=True,
    )
    assert cleared.description is None

    restored = ProjectManager.update(
        project.id,
        basic_user,
        description="Restored context",
        include_description=True,
    )
    assert restored.description == "Restored context"

    with pytest.raises(Exception):
        ProjectManager.update(project.id, basic_user)
    with pytest.raises(Exception):
        ProjectManager.update(project.id, basic_user, name="")
    with pytest.raises(Exception):
        ProjectManager.update(
            project.id,
            basic_user,
            description="d" * 256,
            include_description=True,
        )

    owner_state = ProjectManager.get_access_state(project.id, basic_user)
    assert owner_state is not None
    assert owner_state.has_access
    assert owner_state.pending_request is None

    requester_state = ProjectManager.get_access_state(project.id, admin_user)
    assert requester_state is not None
    assert not requester_state.has_access
    assert requester_state.pending_request is None

    access_request = ProjectManager.request_access(project.id, admin_user)
    pending_state = ProjectManager.get_access_state(project.id, admin_user)
    assert pending_state is not None
    assert not pending_state.has_access
    assert pending_state.pending_request is not None
    assert pending_state.pending_request.id == access_request.id

    assert ProjectManager.cancel_access_request(project.id, admin_user)
    canceled_state = ProjectManager.get_access_state(project.id, admin_user)
    assert canceled_state is not None
    assert not canceled_state.has_access
    assert canceled_state.access_request is None
    assert canceled_state.pending_request is None

    second_request = ProjectManager.request_access(project.id, admin_user)
    ProjectManager.resolve_access_request(
        project.id,
        second_request.id,
        approve=False,
        user_performing_action=basic_user,
    )
    denied_state = ProjectManager.get_access_state(project.id, admin_user)
    assert denied_state is not None
    assert not denied_state.has_access
    assert denied_state.access_request is not None
    assert denied_state.access_request.id == second_request.id
    assert denied_state.access_request.status.value == "DENIED"
    assert denied_state.pending_request is None

    third_request = ProjectManager.request_access(project.id, admin_user)
    re_requested_state = ProjectManager.get_access_state(project.id, admin_user)
    assert re_requested_state is not None
    assert re_requested_state.access_request is not None
    assert re_requested_state.access_request.id == third_request.id
    assert re_requested_state.access_request.status.value == "PENDING"
    assert re_requested_state.pending_request is not None
    ProjectManager.resolve_access_request(
        project.id,
        third_request.id,
        approve=True,
        user_performing_action=basic_user,
    )
    approved_state = ProjectManager.get_access_state(project.id, admin_user)
    assert approved_state is not None
    assert approved_state.has_access
    assert approved_state.pending_request is None

    assert ProjectManager.get_access_state(999999, admin_user) is None


def test_collaborative_project_access(
    basic_user: DATestUser,
    admin_user: DATestUser,
) -> None:
    project = ProjectManager.create(
        name="Collaborative Project",
        user_performing_action=basic_user,
    )
    assert ProjectManager.get(project.id, admin_user) is None

    ProjectManager.update_sharing(
        project.id,
        organization_permission=None,
        user_shares=[{"user_id": admin_user.id, "permission": "VIEWER"}],
        group_shares=[],
        user_performing_action=basic_user,
    )
    viewer_project = ProjectManager.get(project.id, admin_user)
    assert viewer_project is not None
    assert viewer_project.user_permission.value == "VIEWER"
    with pytest.raises(Exception):
        ProjectManager.set_instructions(project.id, "Not allowed", admin_user)
    assert not ProjectManager.delete(project.id, admin_user)

    ProjectManager.update_sharing(
        project.id,
        organization_permission=None,
        user_shares=[{"user_id": admin_user.id, "permission": "EDITOR"}],
        group_shares=[],
        user_performing_action=basic_user,
    )
    assert (
        ProjectManager.set_instructions(project.id, "Shared context", admin_user)
        == "Shared context"
    )
    editor_project = ProjectManager.get(project.id, admin_user)
    assert editor_project is not None
    assert editor_project.user_permission.value == "EDITOR"

    ProjectManager.update_sharing(
        project.id,
        organization_permission="VIEWER",
        user_shares=[],
        group_shares=[],
        user_performing_action=basic_user,
    )
    organization_project = ProjectManager.get(project.id, admin_user)
    assert organization_project is not None
    assert organization_project.user_permission.value == "VIEWER"

    ProjectManager.update_sharing(
        project.id,
        organization_permission=None,
        user_shares=[],
        group_shares=[],
        user_performing_action=basic_user,
    )
    access_request = ProjectManager.request_access(project.id, admin_user)
    owner_sharing = ProjectManager.get_sharing(project.id, basic_user)
    assert [request.id for request in owner_sharing.join_requests] == [
        access_request.id
    ]

    ProjectManager.resolve_access_request(
        project.id,
        access_request.id,
        approve=True,
        user_performing_action=basic_user,
    )
    approved_project = ProjectManager.get(project.id, admin_user)
    assert approved_project is not None
    assert approved_project.user_permission.value == "VIEWER"
