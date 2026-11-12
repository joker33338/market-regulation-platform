"""Bearer身份与数据owner分离；私密配置每次请求重新核验，默认不授予审核权限。"""
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel
import hmac
import json
from pathlib import Path
import re

from qa_core.document_parsing.mineru_client import MinerUError


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}', value) is not None


class PrincipalInfo(BaseModel):
    principal_id: str
    owner_id: str | None
    roles: list[Literal['USER','REVIEWER','ADMIN']]
    review_owner_scopes: list[str]
    credential_status: Literal['active','disabled','revoked']
    document_delete_owner_scopes: list[str] = []


@dataclass(frozen=True)
class Principal:
    principal_id: str
    owner_id: str | None
    roles: frozenset[str]
    review_owner_scopes: tuple[str, ...]
    credential_status: str
    document_delete_owner_scopes: tuple[str, ...] = ()

    @property
    def read_owners(self):
        owners = ([self.owner_id] if self.owner_id else [])
        if 'REVIEWER' in self.roles:
            owners.extend(self.review_owner_scopes)
        return tuple(sorted(set(owners)))

    def can_delete(self, owner_id):
        return self.credential_status == 'active' and 'ADMIN' in self.roles and self.owner_id == owner_id and owner_id in self.document_delete_owner_scopes

    def can_review(self, owner_id):
        return self.credential_status == 'active' and 'REVIEWER' in self.roles and owner_id in self.review_owner_scopes


def owner_selector(principal):
    scopes = principal.read_owners
    return scopes[0] if len(scopes) == 1 else scopes


def data_owner(principal, row):
    owner = row.get('source_location', {}).get('owner_id')
    if owner not in principal.read_owners:
        raise MinerUError('document_not_found', 404)
    return owner


class AuthRegistry:
    def __init__(self, records, loader=None):
        self._records = self.validate(records)
        self._loader = loader

    @staticmethod
    def validate(records):
        try:
            if not isinstance(records, dict) or not records:
                raise ValueError()
            result = []
            principals = set()
            user_owners = set()
            for token, entry in records.items():
                if not isinstance(token, str) or len(token) < 32:
                    raise ValueError()
                if isinstance(entry, str):
                    if not identifier(entry):
                        raise ValueError()
                    value = Principal('legacy:'+entry, entry, frozenset({'USER'}), (), 'active')
                else:
                    if not isinstance(entry, dict) or not ({'principal_id','owner_id','roles','review_owner_scopes','credential_status'} <= set(entry) <= {'principal_id','owner_id','roles','review_owner_scopes','credential_status','document_delete_owner_scopes'}):
                        raise ValueError()
                    pid, owner = entry['principal_id'], entry['owner_id']
                    roles, scopes, status = entry['roles'], entry['review_owner_scopes'], entry['credential_status']
                    if not identifier(pid) or (owner is not None and not identifier(owner)):
                        raise ValueError()
                    if not isinstance(roles,list) or not all(role in ('USER','REVIEWER','ADMIN') for role in roles):
                        raise ValueError()
                    if not isinstance(scopes,list) or not all(identifier(scope) for scope in scopes):
                        raise ValueError()
                    if status not in ('active','disabled','revoked') or ('USER' in roles and owner is None):
                        raise ValueError()
                    delete_scopes=entry.get('document_delete_owner_scopes',[])
                    if not isinstance(delete_scopes,list) or not all(identifier(scope) for scope in delete_scopes):
                        raise ValueError()
                    value = Principal(pid,owner,frozenset(roles),tuple(sorted(set(scopes))),status,tuple(sorted(set(delete_scopes))))
                if value.principal_id in principals:
                    raise ValueError()
                if 'USER' in value.roles:
                    if value.owner_id in user_owners:
                        raise ValueError()
                    user_owners.add(value.owner_id)
                principals.add(value.principal_id)
                result.append((token,value))
            return tuple(result)
        except (TypeError, ValueError):
            raise MinerUError('api_auth_configuration_required',503) from None

    def replace(self, records):
        # 仅供内部配置装载/测试使用，不提供公开账号或授权修改接口。
        validated = self.validate(records)
        self._records, self._loader = validated, None

    def resolve(self, token):
        try:
            records = self.validate(self._loader()) if self._loader else self._records
        except Exception:
            raise MinerUError('auth_configuration_unavailable',503) from None
        for expected, principal in records:
            if hmac.compare_digest(token.encode(),expected.encode()) and principal.credential_status == 'active':
                return principal
        raise MinerUError('unauthorized',401)


def runtime_credentials(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if 'PARSING_API_TOKENS_JSON' in value:
        value = value['PARSING_API_TOKENS_JSON']
        return json.loads(value) if isinstance(value,str) else value
    return value
