"""Fail-closed adapter admission; no imports or execution before authorization.

The host, not adapter metadata or a customer request, supplies an immutable
approval manifest. This module never grants authority to execute side effects.
"""
import hashlib
import importlib
import json
import re
from pathlib import Path


class AdapterDenied(PermissionError):
    pass


_ID = re.compile(r'^[a-z][a-z0-9-]{1,63}$')
_VERSION = re.compile(r'^\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?$')
_SHA = re.compile(r'^[0-9a-f]{64}$')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def authorize_adapter(adapter_id, *, catalog_path, approvals_path, host_scope, capability):
    """Return pinned approved metadata; reject all incomplete or untrusted inputs."""
    if not isinstance(adapter_id, str) or not _ID.fullmatch(adapter_id):
        raise AdapterDenied('INVALID_ADAPTER_ID')
    if not isinstance(host_scope, str) or not host_scope.strip():
        raise AdapterDenied('HOST_SCOPE_REQUIRED')
    if not isinstance(capability, str) or not capability.strip():
        raise AdapterDenied('CAPABILITY_REQUIRED')
    try:
        catalog = _read(catalog_path)
        approvals = _read(approvals_path)
    except (OSError, ValueError, TypeError) as exc:
        raise AdapterDenied('APPROVAL_DATA_UNAVAILABLE') from exc
    if catalog.get('schema_version') != 1 or approvals.get('schema_version') != 1:
        raise AdapterDenied('INVALID_POLICY_SCHEMA')
    entries = catalog.get('adapters', [])
    records = approvals.get('approvals', [])
    if not isinstance(entries, list) or not isinstance(records, list):
        raise AdapterDenied('INVALID_POLICY_FORMAT')
    matching = [x for x in entries if isinstance(x, dict) and x.get('id') == adapter_id]
    approved = [x for x in records if isinstance(x, dict) and x.get('id') == adapter_id]
    if len(matching) != 1 or len(approved) != 1:
        raise AdapterDenied('NOT_UNIQUELY_APPROVED')
    entry, record = matching[0], approved[0]
    if entry.get('status') != 'approved' or record.get('status') != 'approved':
        raise AdapterDenied('ADAPTER_NOT_APPROVED')
    version, digest = record.get('version'), record.get('sha256')
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise AdapterDenied('VERSION_NOT_PINNED')
    if not isinstance(digest, str) or not _SHA.fullmatch(digest):
        raise AdapterDenied('DIGEST_NOT_PINNED')
    if entry.get('approved_version') != version:
        raise AdapterDenied('VERSION_MISMATCH')
    if record.get('module') != entry.get('module'):
        raise AdapterDenied('MODULE_MISMATCH')
    if record.get('host_scope') != host_scope:
        raise AdapterDenied('SCOPE_MISMATCH')
    if capability not in record.get('capabilities', []):
        raise AdapterDenied('CAPABILITY_DENIED')
    if not record.get('reviewer') or not record.get('evidence'):
        raise AdapterDenied('REVIEW_EVIDENCE_REQUIRED')
    module_path = record.get('source_path')
    if not isinstance(module_path, str):
        raise AdapterDenied('SOURCE_NOT_PINNED')
    root = Path(catalog_path).resolve().parent.parent
    source = (root / module_path).resolve()
    if not source.is_relative_to(root) or not source.is_file() or source.suffix != '.py':
        raise AdapterDenied('SOURCE_OUTSIDE_REPOSITORY')
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise AdapterDenied('SOURCE_DIGEST_MISMATCH')
    return dict(record)


def load_approved_adapter(adapter_id, *, catalog_path, approvals_path, host_scope, capability):
    """Import only after all admission checks; host still owns effect authorization."""
    record = authorize_adapter(adapter_id, catalog_path=catalog_path,
        approvals_path=approvals_path, host_scope=host_scope, capability=capability)
    return importlib.import_module(record['module'])
