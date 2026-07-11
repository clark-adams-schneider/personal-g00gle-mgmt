import os
from typing import Optional, Any, Dict, List
import pulumi
from pulumi.dynamic import ResourceProvider, CreateResult, ReadResult, UpdateResult, DiffResult
from ..auth import get_google_service

DRIVE_SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/spreadsheets'
]

def get_drive_service(client_secrets_path: str, token_path: str):
    return get_google_service(
        api_name='drive',
        api_version='v3',
        client_secrets_path=client_secrets_path,
        token_path=token_path,
        scopes=DRIVE_SCOPES
    )

class FolderProvider(ResourceProvider):
    def create(self, inputs: Dict[str, Any]) -> CreateResult:
        name = inputs.get('name')
        parent = inputs.get('parent')
        client_secrets_path = inputs.get('client_secrets_path')
        token_path = inputs.get('token_path')
        description = inputs.get('description')
        folder_color_rgb = inputs.get('folder_color_rgb')
        permissions = inputs.get('permissions') or []
        mime_type = inputs.get('mime_type') or 'application/vnd.google-apps.folder'
        source = inputs.get('source')

        if not client_secrets_path or not token_path:
            raise ValueError("client_secrets_path and token_path must be provided")

        service = get_drive_service(client_secrets_path, token_path)

        # Prepare media upload if source file exists
        media = None
        if source and os.path.exists(source):
            from googleapiclient.http import MediaFileUpload
            media = MediaFileUpload(
                source,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if mime_type == 'application/vnd.google-apps.spreadsheet' else 'application/octet-stream',
                resumable=True
            )

        # Drift logic: Search if resource already exists under parent/root with same name and mimeType
        query = f"mimeType = '{mime_type}' and name = '{name}' and trashed = false"
        if parent:
            query += f" and '{parent}' in parents"
        else:
            query += " and 'root' in parents"

        try:
            results = service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, parents)',
                pageSize=1
            ).execute()
            files = results.get('files', [])
        except Exception as e:
            print(f"Error querying existing resources: {e}")
            files = []

        if files:
            existing_id = files[0]['id']
            print(f"Found existing resource '{name}' with ID {existing_id}. Adopting it.")
            folder_id = existing_id
            
            # Reconcile metadata
            body = {}
            if description:
                body['description'] = description
            if folder_color_rgb and mime_type == 'application/vnd.google-apps.folder':
                body['folderColorRgb'] = folder_color_rgb
            
            try:
                if body:
                    service.files().update(fileId=folder_id, body=body, fields='id').execute()
                # If media is provided, upload/overwrite contents
                if media:
                    service.files().update(fileId=folder_id, media_body=media, fields='id').execute()
                    print(f"Synced adopted resource ID {folder_id} contents from local file.")
            except Exception as e:
                print(f"Failed to update adopted resource: {e}")
        else:
            # Create a new resource
            body = {
                'name': name,
                'mimeType': mime_type
            }
            if parent:
                body['parents'] = [parent]
            if description:
                body['description'] = description
            if folder_color_rgb and mime_type == 'application/vnd.google-apps.folder':
                body['folderColorRgb'] = folder_color_rgb
            
            try:
                if media:
                    folder = service.files().create(body=body, media_body=media, fields='id').execute()
                else:
                    folder = service.files().create(body=body, fields='id').execute()
                folder_id = folder.get('id')
                print(f"Created new resource '{name}' (Type: {mime_type}) with ID {folder_id}.")
            except Exception as e:
                raise RuntimeError(f"Failed to create Google Drive resource '{name}': {e}")

        # Set permissions
        for perm in permissions:
            try:
                service.permissions().create(fileId=folder_id, body=perm).execute()
                print(f"Added permission to {perm.get('emailAddress')} on resource {name}")
            except Exception as pe:
                print(f"Error creating permission {perm} on resource {folder_id}: {pe}")

        return CreateResult(id_=folder_id, outs=inputs)

    def read(self, id_: str, props: Dict[str, Any]) -> ReadResult:
        client_secrets_path = props.get('client_secrets_path')
        token_path = props.get('token_path')

        if not client_secrets_path or not token_path:
            return ReadResult(id_="", outs={})

        try:
            service = get_drive_service(client_secrets_path, token_path)
            folder = service.files().get(
                fileId=id_, 
                fields='id, name, parents, trashed, description, folderColorRgb, mimeType'
            ).execute()
            
            # Check if it was trashed out-of-band
            if folder.get('trashed', False):
                print(f"Resource with ID {id_} is trashed.")
                return ReadResult(id_="", outs={})

            current_parents = folder.get('parents', [])
            current_parent = current_parents[0] if current_parents else None

            # Read permissions
            perms_result = service.permissions().list(
                fileId=id_, 
                fields='permissions(id, emailAddress, role, type)'
            ).execute()
            current_perms = perms_result.get('permissions', [])

            expected_emails = {p.get('emailAddress') for p in props.get('permissions', []) if p.get('emailAddress')}
            matching_perms = []
            for p in current_perms:
                email = p.get('emailAddress')
                if email in expected_emails:
                    matching_perms.append({
                        'role': p.get('role'),
                        'type': p.get('type'),
                        'emailAddress': email
                    })

            outs = props.copy()
            outs['name'] = folder.get('name')
            outs['parent'] = current_parent
            outs['description'] = folder.get('description')
            outs['folder_color_rgb'] = folder.get('folderColorRgb')
            outs['permissions'] = matching_perms
            outs['mime_type'] = folder.get('mimeType')
            return ReadResult(id_=id_, outs=outs)
        except Exception as e:
            print(f"Resource with ID {id_} not found or error occurred during read: {e}")
            return ReadResult(id_="", outs={})

    def diff(self, id_: str, olds: Dict[str, Any], news: Dict[str, Any]) -> DiffResult:
        changes = False
        replaces = []

        if olds.get('name') != news.get('name'):
            changes = True
        if olds.get('parent') != news.get('parent'):
            changes = True
        if olds.get('description') != news.get('description'):
            changes = True
        if olds.get('folder_color_rgb') != news.get('folder_color_rgb'):
            changes = True
        if olds.get('permissions') != news.get('permissions'):
            changes = True
        if olds.get('mime_type') != news.get('mime_type'):
            changes = True
            replaces.append('mime_type')
        if olds.get('source') != news.get('source'):
            changes = True
        if olds.get('source_hash') != news.get('source_hash'):
            changes = True

        return DiffResult(changes=changes, replaces=replaces)

    def update(self, id_: str, olds: Dict[str, Any], news: Dict[str, Any]) -> UpdateResult:
        client_secrets_path = news.get('client_secrets_path')
        token_path = news.get('token_path')

        if not client_secrets_path or not token_path:
            raise ValueError("client_secrets_path and token_path must be provided")

        service = get_drive_service(client_secrets_path, token_path)
        mime_type = news.get('mime_type') or 'application/vnd.google-apps.folder'
        source = news.get('source')
        source_hash = news.get('source_hash')
        old_source_hash = olds.get('source_hash')

        # Update metadata if changed
        body = {}
        if olds.get('name') != news.get('name'):
            body['name'] = news.get('name')
        if olds.get('description') != news.get('description'):
            body['description'] = news.get('description') or ''
        if olds.get('folder_color_rgb') != news.get('folder_color_rgb') and mime_type == 'application/vnd.google-apps.folder':
            body['folderColorRgb'] = news.get('folder_color_rgb') or ''

        if body:
            try:
                service.files().update(fileId=id_, body=body, fields='id').execute()
                print(f"Updated metadata on resource ID {id_}.")
            except Exception as e:
                raise RuntimeError(f"Failed to update resource metadata: {e}")

        # Sync local file updates to Google Drive
        if source and os.path.exists(source) and old_source_hash != source_hash:
            from googleapiclient.http import MediaFileUpload
            media = MediaFileUpload(
                source,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if mime_type == 'application/vnd.google-apps.spreadsheet' else 'application/octet-stream',
                resumable=True
            )
            try:
                service.files().update(fileId=id_, media_body=media, fields='id').execute()
                print(f"Synced updated local file '{source}' to Google Drive file ID {id_}.")
            except Exception as e:
                raise RuntimeError(f"Failed to sync updated local file: {e}")

        # Update parent if changed
        old_parent = olds.get('parent')
        new_parent = news.get('parent')
        if old_parent != new_parent:
            try:
                file_info = service.files().get(fileId=id_, fields='parents').execute()
                current_parents = file_info.get('parents', [])
                
                add_parents = new_parent if new_parent else 'root'
                remove_parents = ",".join(current_parents)
                
                if remove_parents:
                    service.files().update(
                        fileId=id_,
                        addParents=add_parents,
                        removeParents=remove_parents,
                        fields='id'
                    ).execute()
                else:
                    service.files().update(
                        fileId=id_,
                        addParents=add_parents,
                        fields='id'
                    ).execute()
                print(f"Moved resource ID {id_} to new parent '{new_parent}'.")
            except Exception as e:
                raise RuntimeError(f"Failed to move resource parent: {e}")

        # Reconcile permissions
        old_perms = olds.get('permissions') or []
        new_perms = news.get('permissions') or []
        if old_perms != new_perms:
            try:
                perms_result = service.permissions().list(
                    fileId=id_, 
                    fields='permissions(id, emailAddress, role, type)'
                ).execute()
                current_perms = perms_result.get('permissions', [])
                
                for perm in new_perms:
                    email = perm.get('emailAddress')
                    role = perm.get('role')
                    ptype = perm.get('type')
                    
                    match = next((p for p in current_perms if p.get('emailAddress') == email and p.get('role') == role and p.get('type') == ptype), None)
                    if not match:
                        existing = [p for p in current_perms if p.get('emailAddress') == email]
                        for e_p in existing:
                            try:
                                service.permissions().delete(fileId=id_, permissionId=e_p['id']).execute()
                            except Exception:
                                pass
                        service.permissions().create(fileId=id_, body=perm).execute()
                        print(f"Updated permission for {email} to {role} on resource ID {id_}")
                
                for old_perm in old_perms:
                    email = old_perm.get('emailAddress')
                    if not any(n.get('emailAddress') == email for n in new_perms):
                        to_delete = [p for p in current_perms if p.get('emailAddress') == email]
                        for p in to_delete:
                            try:
                                service.permissions().delete(fileId=id_, permissionId=p['id']).execute()
                                print(f"Removed permission for {email} on resource ID {id_}")
                            except Exception:
                                pass
            except Exception as e:
                print(f"Error reconciling permissions: {e}")

        return UpdateResult(outs=news)

    def delete(self, id_: str, props: Dict[str, Any]) -> None:
        client_secrets_path = props.get('client_secrets_path')
        token_path = props.get('token_path')

        if not client_secrets_path or not token_path:
            return

        try:
            service = get_drive_service(client_secrets_path, token_path)
            service.files().update(fileId=id_, body={'trashed': True}).execute()
            print(f"Moved resource with ID {id_} to trash.")
        except Exception as e:
            print(f"Error trashing resource with ID {id_}: {e}")

