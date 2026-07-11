from pathlib import Path
from typing import Any, Dict, Optional

from pulumi.dynamic import (
    CreateResult,
    DiffResult,
    ReadResult,
    ResourceProvider,
    UpdateResult,
)

from ..auth import GoogleApiName, GoogleOAuthScope, get_google_service
from .models import AnyMimeType, FolderInputs, GoogleDriveFileBody, GoogleDriveMimeType

DRIVE_SCOPES = [
    GoogleOAuthScope.DRIVE_FILE,
    GoogleOAuthScope.SPREADSHEETS,
]


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

    def _find_existing(self, service, model: FolderInputs) -> str:
        query = f"mimeType = '{model.mime_type}' and name = '{model.name}' and trashed = false"
        if model.parent:
            query += f" and '{model.parent}' in parents"
        else:
            query += " and 'root' in parents"

        try:
            results = (
                service.files()
                .list(q=query, spaces="drive", fields="files(id)", pageSize=1)
                .execute()
            )
            files = results.get("files", [])
            if files:
                return files[0]["id"]
        except Exception as e:
            print(f"Error querying existing resources: {e}")
        return ""

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

    def _create_resource(self, service, model: FolderInputs, media) -> str:
        body = GoogleDriveFileBody(name=model.name, mimeType=model.mime_type)
        if model.parent:
            body.parents = [model.parent]
        if model.description:
            body.description = model.description
        if model.folder_color_rgb and model.mime_type == GoogleDriveMimeType.FOLDER:
            body.folderColorRgb = model.folder_color_rgb

        kwargs = {"body": body.model_dump(exclude_none=True), "fields": "id"}
        if media:
            kwargs["media_body"] = media

        folder = service.files().create(**kwargs).execute()
        return folder.get("id")

    def _reconcile_permissions(self, service, folder_id: str, model: FolderInputs):
        try:
            perms_result = (
                service.permissions()
                .list(
                    fileId=folder_id, fields="permissions(id, emailAddress, role, type)"
                )
                .execute()
            )
            current_perms = perms_result.get("permissions", [])

            for cp in current_perms:
                if "emailAddress" in cp:
                    try:
                        service.permissions().delete(
                            fileId=folder_id, permissionId=cp["id"]
                        ).execute()
                    except Exception:
                        pass

            for perm in model.permissions:
                service.permissions().create(
                    fileId=folder_id, body=perm.model_dump(exclude_none=True)
                ).execute()
        except Exception as e:
            print(f"Error reconciling permissions: {e}")

    def create(self, inputs: Dict[str, Any]) -> CreateResult:
        model = FolderInputs(**inputs)
        service = get_drive_service(model.client_secrets_path, model.token_path)
        media = self._get_media_upload(model.source, model.mime_type)

        existing_id = self._find_existing(service, model)
        if existing_id:
            folder_id = existing_id
            self._update_metadata(service, folder_id, model, media)
        else:
            folder_id = self._create_resource(service, model, media)

        self._reconcile_permissions(service, folder_id, model)
        return CreateResult(id_=folder_id, outs=inputs)

    def read(self, id_: str, props: Dict[str, Any]) -> ReadResult:
        model = FolderInputs(**props)
        service = get_drive_service(model.client_secrets_path, model.token_path)

        try:
            folder = (
                service.files()
                .get(
                    fileId=id_,
                    fields="id, name, parents, trashed, description, folderColorRgb, mimeType",
                )
                .execute()
            )

            if folder.get("trashed", False):
                return ReadResult(id_="", outs={})

            outs = props.copy()
            outs["name"] = folder.get("name")
            outs["description"] = folder.get("description")
            outs["folder_color_rgb"] = folder.get("folderColorRgb")
            outs["mime_type"] = folder.get("mimeType")

            parents = folder.get("parents", [])
            outs["parent"] = parents[0] if parents else None

            return ReadResult(id_=id_, outs=outs)
        except Exception:
            return ReadResult(id_="", outs={})

    def diff(self, id_: str, olds: Dict[str, Any], news: Dict[str, Any]) -> DiffResult:
        old_m = FolderInputs(**olds)
        new_m = FolderInputs(**news)

        changes = False
        replaces = []
        if old_m.name != new_m.name:
            changes = True
        if old_m.parent != new_m.parent:
            changes = True
        if old_m.description != new_m.description:
            changes = True
        if old_m.folder_color_rgb != new_m.folder_color_rgb:
            changes = True
        if old_m.permissions != new_m.permissions:
            changes = True
        if old_m.source_hash != new_m.source_hash:
            changes = True

        if old_m.mime_type != new_m.mime_type:
            changes = True
            replaces.append("mime_type")

        return DiffResult(changes=changes, replaces=replaces)

    def update(
        self, id_: str, olds: Dict[str, Any], news: Dict[str, Any]
    ) -> UpdateResult:
        old_m = FolderInputs(**olds)
        new_m = FolderInputs(**news)
        service = get_drive_service(new_m.client_secrets_path, new_m.token_path)

        media = None
        if new_m.source and new_m.source_hash != old_m.source_hash:
            media = self._get_media_upload(new_m.source, new_m.mime_type)

        self._update_metadata(service, id_, new_m, media)

        if old_m.parent != new_m.parent:
            file_info = service.files().get(fileId=id_, fields="parents").execute()
            current_parents = file_info.get("parents", [])
            remove_parents = ",".join(current_parents)
            add_parents = new_m.parent if new_m.parent else "root"
            service.files().update(
                fileId=id_,
                addParents=add_parents,
                removeParents=remove_parents,
                fields="id",
            ).execute()

        if old_m.permissions != new_m.permissions:
            self._reconcile_permissions(service, id_, new_m)

        return UpdateResult(outs=news)

    def delete(self, id_: str, props: Dict[str, Any]) -> None:
        model = FolderInputs(**props)
        service = get_drive_service(model.client_secrets_path, model.token_path)
        try:
            body = GoogleDriveFileBody(trashed=True)
            service.files().update(
                fileId=id_, body=body.model_dump(exclude_none=True)
            ).execute()
        except Exception as e:
            print(f"Error trashing resource {id_}: {e}")
