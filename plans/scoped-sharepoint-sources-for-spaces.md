# Scoped SharePoint Sources for Spaces

## Issues to Address

Open WebUI let users pick SharePoint files and folders directly from Microsoft Graph, then copied those files into Open WebUI storage. That made the UI flexible, but it created duplicate file records and a second synchronization path outside Onyx connector indexing and ACL enforcement.

Onyx already has a stronger primitive: the SharePoint connector can fetch selected sites, drives, and `folder_path` scopes. Spaces should build on that connector scope model rather than reintroducing a parallel importer.

## Important Notes

- SharePoint connector scoping already exists for sites, drives, and `folder_path` values.
- Folder-scoped SharePoint fetching currently uses paged traversal, not drive-wide delta. That is acceptable for bounded admin-approved scopes, but large folders need sync-health visibility.
- Current production Graph app credentials can read users, but Graph group reads returned 403. Microsoft `department` is empty for sampled users, while `jobTitle` has useful department-like signals.
- Open WebUI has richer local department groups than current Onyx production. The main authorization gap is identity/group sync, not Space file import.
- Current Onyx `UserProject` is already the Space model. Do not add a second Space table.
- Space access must not bypass document ACL or connected-source governance.

## Implementation Strategy

### 1. Admin-owned SharePoint connector scopes

Admins define approved SharePoint scopes as connector configuration, using explicit include scopes and optional exclude scopes. A scope should represent a tenant/site/drive/folder path, not a copied file bundle.

These scopes should surface as governed hierarchy nodes after indexing. Admin metadata such as tenant label, department label, warnings, curation status, and group visibility belongs in connected-source governance.

### 2. Spaces attach indexed references

A Space may attach:

- an indexed hierarchy node, such as a SharePoint folder scope,
- an indexed document,
- or a local user-uploaded file.

A Space should not copy SharePoint documents into user-file storage. If a user tries to add a SharePoint folder or file that has not been indexed yet, the UI should guide them to request or create an admin-approved connector scope first.

### 3. Effective access rule

For every retrieval from a Space:

```text
effective_access = space_access AND document_acl_access AND connected_source_governance_access
```

Sharing a Space grants access to the Space shell only. It never grants access to a forbidden SharePoint document or folder.

### 4. Default model per Space

Add an optional `default_model_configuration_id` to `UserProject`. In chat resolution, it should apply after explicit session/model overrides and custom assistant defaults, but before the user's personal default. This lets a Space default to a model appropriate for its workflow without overriding a user's deliberate per-chat choice.

### 5. Naming cleanup

Keep database and historical API names as `project` where churn would be high, but UI copy should consistently say Space. New docs and new user-facing text should use Space.

## Tests

- Backend unit or integration coverage for project snapshot serialization and metadata update of `default_model_configuration_id`.
- TypeScript checks for Space metadata and model selector plumbing.
- Manual runtime validation: create or update a Space default model, enter the Space, confirm the chat model defaults to that selection, then confirm a manual chat model override still wins.
