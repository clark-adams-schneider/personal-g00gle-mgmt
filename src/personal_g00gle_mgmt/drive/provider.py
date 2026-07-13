from pathlib import Path
from typing import List, Optional, Set

from pulumi.dynamic import (
    CreateResult,
    DiffResult,
    ReadResult,
    ResourceProvider,
    UpdateResult,
)

from ..auth import GoogleApiName, GoogleOAuthScope, get_google_service
from .models import (
    AnyMimeType,
    DriveFileParentsPatch,
    DrivePulumiAppPropertyKey,
    FolderInputs,
    GoogleDriveAppPropertyQuery,
    GoogleDriveFileBody,
    GoogleDriveFileParentsResponse,
    GoogleDriveFileResponse,
    GoogleDriveMimeType,
    GoogleDriveSearchQuery,
    ManagedResourceMarker,
    PermissionModel,
    PermissionResponse,
)

DRIVE_SCOPES = [
    GoogleOAuthScope.DRIVE_FILE,
]


class ProtectedResourceDeletionError(RuntimeError):
    pass


def get_drive_service(client_secrets_path: Path, token_path: Path):
    return get_google_service(
        api_name=GoogleApiName.DRIVE,
        api_version="v3",
        client_secrets_path=client_secrets_path,
        token_path=token_path,
        scopes=DRIVE_SCOPES,
    )


class FolderProvider(ResourceProvider):
    def _get_media_upload(self, source: Optional[Path], mime_type: AnyMimeType):
        if not source or not source.exists():
            return None
        from googleapiclient.http import MediaFileUpload

        upload_mime = mime_type.upload_mime_type.value
        return MediaFileUpload(str(source), mimetype=upload_mime, resumable=True)

    def _search_single_file(self, service, query_string: str) -> str:
        try:
            results = (
                service.files()
                .list(q=query_string, spaces="drive", fields="files(id)")
                .execute()
            )
            files = results.get("files", [])
            if files:
                return files[0]["id"]
        except Exception as e:
            print(f"Error querying Drive: {e}")
        return ""

    def _find_by_resource_key(self, service, model: FolderInputs) -> str:
        query = GoogleDriveAppPropertyQuery(
            key=DrivePulumiAppPropertyKey.RESOURCE_KEY, value=model.resource_key
        )
        return self._search_single_file(service, query.query_string)

    def _find_by_name_and_parent(self, service, model: FolderInputs) -> str:
        query = GoogleDriveSearchQuery(
            mime_type=model.mime_type, name=model.name, parent=model.parent
        )
        return self._search_single_file(service, query.query_string)

    def _find_existing(self, service, model: FolderInputs) -> str:
        """Find the Drive file this resource manages, if one already exists.

        Tries the stable `resource_key` tag first so a resource already known
        to Pulumi is found even after being renamed or moved outside of it.
        Only falls back to matching by (name, parent, mimeType) for adopting
        a pre-existing, not-yet-Pulumi-managed file on first creation.
        """
        return self._find_by_resource_key(
            service, model
        ) or self._find_by_name_and_parent(service, model)

    def _ensure_resource_key_tag(self, service, folder_id: str, model: FolderInputs):
        marker = ManagedResourceMarker(resource_key=model.resource_key)
        body = GoogleDriveFileBody(appProperties=marker.app_properties)
        service.files().update(
            fileId=folder_id, body=body.model_dump(exclude_none=True), fields="id"
        ).execute()

    def _update_metadata(self, service, folder_id: str, model: FolderInputs, media):
        body = GoogleDriveFileBody()
        if model.description is not None:
            body.description = model.description
        if model.folder_color_rgb and model.mime_type == GoogleDriveMimeType.FOLDER:
            body.folderColorRgb = model.folder_color_rgb

        body_dict = body.model_dump(exclude_none=True)
        if body_dict:
            service.files().update(
                fileId=folder_id, body=body_dict, fields="id"
            ).execute()
        if media:
            service.files().update(
                fileId=folder_id, media_body=media, fields="id"
            ).execute()

    @staticmethod
    def _resolve_target_parents(model: FolderInputs) -> Set[str]:
        target_parents = set(model.extra_parent_ids)
        if model.parent:
            target_parents.add(model.parent)
        return target_parents

    def _reconcile_parents(self, service, folder_id: str, model: FolderInputs) -> None:
        target_parents = self._resolve_target_parents(model) or {"root"}
        file_info_raw = (
            service.files().get(fileId=folder_id, fields="parents").execute()
        )
        current_parents = set(GoogleDriveFileParentsResponse(**file_info_raw).parents)

        add_parents = target_parents - current_parents
        remove_parents = current_parents - target_parents
        if not add_parents and not remove_parents:
            return

        patch = DriveFileParentsPatch.from_parent_diff(
            folder_id, add_parents, remove_parents
        )
        service.files().update(**patch.model_dump(exclude_none=True)).execute()

    def _create_resource(self, service, model: FolderInputs, media) -> str:
        marker = ManagedResourceMarker(resource_key=model.resource_key)
        body = GoogleDriveFileBody(
            name=model.name,
            mimeType=model.mime_type,
            appProperties=marker.app_properties,
        )
        target_parents = self._resolve_target_parents(model)
        if target_parents:
            body.parents = sorted(target_parents)
        if model.description:
            body.description = model.description
        if model.folder_color_rgb and model.mime_type == GoogleDriveMimeType.FOLDER:
            body.folderColorRgb = model.folder_color_rgb

        body_dict = body.model_dump(exclude_none=True)
        if media:
            folder = (
                service.files()
                .create(body=body_dict, media_body=media, fields="id")
                .execute()
            )
        else:
            folder = service.files().create(body=body_dict, fields="id").execute()

        return folder.get("id")

    def _list_permissions(self, service, folder_id: str) -> List[PermissionResponse]:
        perms_result = (
            service.permissions()
            .list(fileId=folder_id, fields="permissions(id, emailAddress, role, type)")
            .execute()
        )
        return [
            PermissionResponse(**cp_raw)
            for cp_raw in perms_result.get("permissions", [])
        ]

    def _delete_permission(self, service, folder_id: str, permission_id: str) -> None:
        try:
            service.permissions().delete(
                fileId=folder_id, permissionId=permission_id
            ).execute()
        except Exception:
            pass

    def _create_permission(
        self, service, folder_id: str, permission: PermissionModel
    ) -> None:
        service.permissions().create(
            fileId=folder_id, body=permission.model_dump(exclude_none=True)
        ).execute()

    def _reconcile_permissions(self, service, folder_id: str, model: FolderInputs):
        """Diff live permissions against the declared set and apply only the delta.

        Only permissions with an emailAddress are Pulumi-managed here (domain-
        or anyone-scoped grants are left untouched); recreating the full list
        on every change would rate-limit large trees and briefly leave the
        file with no permissions at all mid-reconcile.
        """
        try:
            current = self._list_permissions(service, folder_id)
        except Exception as e:
            print(f"Error listing permissions: {e}")
            return

        current_by_key = {
            PermissionModel(
                emailAddress=cp.emailAddress, role=cp.role, type=cp.type
            ): cp.id
            for cp in current
            if cp.emailAddress and cp.role and cp.type
        }
        target = set(model.permissions)

        for key, permission_id in current_by_key.items():
            if key not in target:
                self._delete_permission(service, folder_id, permission_id)

        for perm in target:
            if perm not in current_by_key:
                self._create_permission(service, folder_id, perm)

    def create(self, inputs: FolderInputs) -> CreateResult:
        model = FolderInputs.model_validate(inputs)
        service = get_drive_service(model.client_secrets_path, model.token_path)
        media = self._get_media_upload(model.source, model.mime_type)

        existing_id = self._find_existing(service, model)
        if existing_id:
            folder_id = existing_id
            self._update_metadata(service, folder_id, model, media)
            self._reconcile_parents(service, folder_id, model)
            self._ensure_resource_key_tag(service, folder_id, model)
        else:
            folder_id = self._create_resource(service, model, media)

        self._reconcile_permissions(service, folder_id, model)
        return CreateResult(id_=folder_id, outs=model.model_dump(mode="json"))

    def read(self, id_: str, props: FolderInputs) -> ReadResult:
        model = FolderInputs.model_validate(props)
        service = get_drive_service(model.client_secrets_path, model.token_path)

        try:
            folder_raw = (
                service.files()
                .get(
                    fileId=id_,
                    fields="id, name, parents, trashed, description, folderColorRgb, mimeType",
                )
                .execute()
            )

            file_resp = GoogleDriveFileResponse(**folder_raw)

            if file_resp.trashed:
                return ReadResult(id_="", outs={})

            model.name = file_resp.name
            model.description = file_resp.description
            if file_resp.folderColorRgb:
                model.folder_color_rgb = file_resp.folderColorRgb.value
            else:
                model.folder_color_rgb = None

            model.mime_type = file_resp.mimeType

            primary_parent = (
                model.parent
                if model.parent in file_resp.parents
                else (file_resp.parents[0] if file_resp.parents else None)
            )
            model.parent = primary_parent
            model.extra_parent_ids = sorted(
                p for p in file_resp.parents if p != primary_parent
            )

            return ReadResult(id_=id_, outs=model.model_dump(mode="json"))
        except Exception:
            return ReadResult(id_="", outs={})

    def diff(self, id_: str, olds: FolderInputs, news: FolderInputs) -> DiffResult:
        old_m = FolderInputs.model_validate(olds)
        new_m = FolderInputs.model_validate(news)

        ignored_fields = {"client_secrets_path", "token_path"}
        changed_fields = [
            field
            for field in FolderInputs.model_fields
            if field not in ignored_fields
            and getattr(old_m, field) != getattr(new_m, field)
        ]

        changes = len(changed_fields) > 0
        replaces = ["mime_type"] if "mime_type" in changed_fields else []

        return DiffResult(changes=changes, replaces=replaces)

    def update(self, id_: str, olds: FolderInputs, news: FolderInputs) -> UpdateResult:
        old_m = FolderInputs.model_validate(olds)
        new_m = FolderInputs.model_validate(news)
        service = get_drive_service(new_m.client_secrets_path, new_m.token_path)

        media = None
        if new_m.source and new_m.source_hash != old_m.source_hash:
            media = self._get_media_upload(new_m.source, new_m.mime_type)

        self._update_metadata(service, id_, new_m, media)

        if old_m.resource_key != new_m.resource_key:
            self._ensure_resource_key_tag(service, id_, new_m)

        if self._resolve_target_parents(old_m) != self._resolve_target_parents(new_m):
            self._reconcile_parents(service, id_, new_m)

        if old_m.permissions != new_m.permissions:
            self._reconcile_permissions(service, id_, new_m)

        return UpdateResult(outs=new_m.model_dump(mode="json"))

    def delete(self, id_: str, props: FolderInputs) -> None:
        model = FolderInputs.model_validate(props)
        if model.protect:
            raise ProtectedResourceDeletionError(
                f"Refusing to delete protected Drive resource {model.name!r} "
                f"(id={id_}); remove _protect from the spec to allow deletion."
            )
        service = get_drive_service(model.client_secrets_path, model.token_path)
        try:
            body = GoogleDriveFileBody(trashed=True)
            service.files().update(
                fileId=id_, body=body.model_dump(exclude_none=True)
            ).execute()
        except Exception as e:
            print(f"Error trashing resource {id_}: {e}")
