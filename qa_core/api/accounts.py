"""私密文件账号与短期Bearer会话；密码加盐哈希，权限每次请求重新读取。"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import time
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from filelock import FileLock, Timeout
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from qa_core.document_parsing.mineru_client import MinerUError
from .common import guarded, page_of
from .principals import AuthRegistry, PrincipalInfo, principal_info

PASSWORD_ITERATIONS=600000
LiteralRole=Literal['USER','REVIEWER','ADMIN']


def hash_password(password):
    salt=secrets.token_hex(16)
    value=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),PASSWORD_ITERATIONS).hex()
    return f'pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${value}'


def check_password(password, encoded):
    kind,iterations,salt,expected=encoded.split('$')
    value=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(iterations)).hex()
    return hmac.compare_digest(value,expected)


def atomic_json(path,value):
    temporary=path.parent/(uuid4().hex+'.tmp')
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False)
        stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


class AccountStore:
    def __init__(self,root):
        self.root=Path(root)/'.auth-sessions'
        self.filename=os.getenv('AUTH_ACCOUNTS_FILE')

    @property
    def path(self):
        if not self.filename:
            raise MinerUError('password_login_not_configured',503)
        return Path(self.filename)

    def load(self):
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(value,dict) or set(value)!={'schema_version','accounts','events'} or value['schema_version']!=1 or not isinstance(value['accounts'],list) or not isinstance(value['events'],list):
                raise ValueError()
            names=set();records={}
            for index,item in enumerate(value['accounts']):
                if set(item)!={'username','password_hash','principal_id','owner_id','roles','review_owner_scopes','credential_status','document_delete_owner_scopes'}:
                    raise ValueError()
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]{2,63}',item['username']) or item['username'].casefold() in names:
                    raise ValueError()
                names.add(item['username'].casefold())
                if not re.fullmatch(r'pbkdf2_sha256\$[0-9]{6,7}\$[a-f0-9]{32}\$[a-f0-9]{64}',item['password_hash']):
                    raise ValueError()
                if not 600000<=int(item['password_hash'].split('$')[1])<=2000000:
                    raise ValueError()
                records[str(index).zfill(32)]={key:item[key] for key in item if key not in {'username','password_hash'}}
            principals=AuthRegistry.validate(records) if records else ()
            self.check_reserved([identity for _,identity in principals])
            return value,{identity.principal_id:identity for _,identity in principals}
        except MinerUError:
            raise
        except Exception:
            raise MinerUError('account_store_unavailable',503) from None

    @contextmanager
    def locked(self):
        try:
            with FileLock(str(self.path)+'.lock',timeout=3):
                yield
        except Timeout:
            raise MinerUError('account_store_busy',409) from None

    @staticmethod
    def public(item):
        return {key:value for key,value in item.items() if key!='password_hash'}

    def change(self,operator_id,action,callback):
        with self.locked():
            value,_=self.load()
            before={item['principal_id']:self.public(item) for item in value['accounts']}
            before_passwords={item['principal_id']:item['password_hash'] for item in value['accounts']}
            result=callback(value)
            # 变更与审计同一原子提交，日志不包含密码或密码哈希。
            value['events'].append({'event_id':uuid4().hex,'timestamp':datetime.now(timezone.utc).isoformat(),
                                   'operator_id':operator_id,'action':action,'target_id':result['principal_id'],
                                   'roles':result['roles'],'credential_status':result['credential_status'],
                                   'before':before.get(result['principal_id']),'after':self.public(result),
                                   'password_changed':before_passwords.get(result['principal_id'])!=result['password_hash']})
            self.validate_value(value)
            atomic_json(self.path,value)
            return self.public(result)

    def validate_value(self,value):
        usernames=set();records={}
        for index,item in enumerate(value['accounts']):
            if item['username'].casefold() in usernames:
                raise MinerUError('username_exists',409)
            usernames.add(item['username'].casefold())
            records[str(index).zfill(32)]={key:item[key] for key in item if key not in {'username','password_hash'}}
        try:
            principals=AuthRegistry.validate(records)
        except MinerUError:
            raise MinerUError('invalid_account_permissions',422) from None
        try:
            self.check_reserved([identity for _,identity in principals])
        except ValueError:
            raise MinerUError('account_identity_reserved',409) from None
        if not any(item['credential_status']=='active' and 'ADMIN' in item['roles'] for item in value['accounts']):
            raise MinerUError('last_active_admin_required',409)

    def check_reserved(self,identities):
        registry=getattr(self,'legacy_registry',None)
        existing=registry.principals() if registry else ()
        principal_ids={identity.principal_id for identity in existing}
        user_owners={identity.owner_id for identity in existing if 'USER' in identity.roles}
        if any(identity.principal_id in principal_ids or 'USER' in identity.roles and identity.owner_id in user_owners for identity in identities):
            raise ValueError('新账号不能占用已有独立身份或普通用户owner')

    def rate_limit(self,username,client):
        self.root.mkdir(parents=True,exist_ok=True)
        now=time.time()
        for key,limit in ((['username',username.casefold()],8),(['client',client],100)):
            path=self.root/('rate-'+hashlib.sha256(json.dumps(key).encode()).hexdigest()+'.json')
            with FileLock(str(path)+'.lock',timeout=2):
                history=json.loads(path.read_text()) if path.exists() else []
                history=[stamp for stamp in history if stamp>now-300]
                if len(history)>=limit:
                    raise MinerUError('login_rate_limited',429)
                history.append(now);atomic_json(path,history)

    def login(self,username,password,client):
        self.rate_limit(username,client)
        value,principals=self.load()
        item=next((item for item in value['accounts'] if hmac.compare_digest(item['username'].casefold(),username.casefold())),None)
        dummy='pbkdf2_sha256$600000$'+'0'*32+'$'+'0'*64
        valid=check_password(password,item['password_hash'] if item else dummy)
        if not valid or item is None or item['credential_status']!='active':
            raise MinerUError('invalid_credentials',401)
        token='sess_'+secrets.token_urlsafe(32)
        identifier=hashlib.sha256(token.encode()).hexdigest()
        ttl=3600
        atomic_json(self.root/(identifier+'.json'),{'principal_id':item['principal_id'],
                    'credential_digest':hashlib.sha256(item['password_hash'].encode()).hexdigest(),
                    'expires_at':time.time()+ttl,'revoked':False})
        return token,ttl,principals[item['principal_id']]

    def resolve(self,token):
        if not re.fullmatch(r'sess_[A-Za-z0-9_-]{43}',token):
            raise MinerUError('unauthorized',401)
        try:
            path=self.root/(hashlib.sha256(token.encode()).hexdigest()+'.json')
            if not path.is_file():
                raise MinerUError('unauthorized',401)
            session=json.loads(path.read_text())
            if session['revoked'] or session['expires_at']<=time.time():
                raise MinerUError('unauthorized',401)
            value,principals=self.load()
            item=next((item for item in value['accounts'] if item['principal_id']==session['principal_id']),None)
            if (item is None or item['credential_status']!='active' or not hmac.compare_digest(
                    session['credential_digest'],hashlib.sha256(item['password_hash'].encode()).hexdigest())):
                raise MinerUError('unauthorized',401)
            return principals[item['principal_id']]
        except MinerUError:
            raise
        except Exception:
            raise MinerUError('session_store_unavailable',503) from None

    def logout(self,token):
        self.resolve(token)
        path=self.root/(hashlib.sha256(token.encode()).hexdigest()+'.json')
        with FileLock(str(path)+'.lock',timeout=2):
            value=json.loads(path.read_text());value['revoked']=True;atomic_json(path,value)


class LoginRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    username: str=Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.@-]{2,63}$')
    password: SecretStr=Field(min_length=1,max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str='bearer'
    expires_in: int
    principal: PrincipalInfo


class AccountCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    username: str=Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.@-]{2,63}$')
    password: SecretStr=Field(min_length=12,max_length=256)
    owner_id: str | None=None
    roles: list[LiteralRole]=Field(default_factory=lambda:['USER'])
    review_owner_scopes: list[str]=Field(default_factory=list)
    document_delete_owner_scopes: list[str]=Field(default_factory=list)


class AccountUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    password: SecretStr | None=Field(default=None,min_length=12,max_length=256)
    roles: list[LiteralRole] | None=None
    review_owner_scopes: list[str] | None=None
    document_delete_owner_scopes: list[str] | None=None
    credential_status: str | None=Field(default=None,pattern='^(active|disabled|revoked)$')


class AccountView(BaseModel):
    username: str
    principal_id: str
    owner_id: str | None
    roles: list[LiteralRole]
    review_owner_scopes: list[str]
    document_delete_owner_scopes: list[str]
    credential_status: Literal['active','disabled','revoked']


class AccountPage(BaseModel):
    list: list[AccountView]
    total: int
    page: int
    page_size: int
    source: str


class AccountEvent(BaseModel):
    event_id: str
    timestamp: str
    operator_id: str
    target_id: str
    action: str
    roles: list[LiteralRole]
    credential_status: str
    before: AccountView | None=None
    after: AccountView | None=None
    password_changed: bool=False


class AccountEventPage(BaseModel):
    list: list[AccountEvent]
    total: int
    page: int
    page_size: int
    source: str


class RoleDefinition(BaseModel):
    role: LiteralRole
    label: str
    data_scope: str
    review_write: bool
    account_management: bool


class RoleCatalog(BaseModel):
    admin_policy: Literal['all_permissions']
    list: list[RoleDefinition]
    safety_gates: list[str]


class LogoutResponse(BaseModel):
    revoked: bool


def register_accounts(app,principal,store):
    from .document_delete import DocumentDeletionError
    router=APIRouter(tags=['accounts'],responses={code:{'model':DocumentDeletionError} for code in (401,403,404,409,422,429,503)})

    def require_admin(identity=Depends(principal)):
        if not identity.is_admin:
            raise MinerUError('admin_required',403)
        return identity

    @router.get('/api/auth/roles',response_model=RoleCatalog)
    def roles(identity=Depends(principal)):
        return {'admin_policy':'all_permissions','list':[
            {'role':'USER','label':'普通用户','data_scope':'own','review_write':False,'account_management':False},
            {'role':'REVIEWER','label':'审核员','data_scope':'own_and_explicit_review_scopes','review_write':True,'account_management':False},
            {'role':'ADMIN','label':'管理员','data_scope':'all','review_write':True,'account_management':True}],
            'safety_gates':['evidence_protection','quality_validation','optimistic_version','audit_trail','deployment_approval']}

    @router.post('/api/auth/login',response_model=LoginResponse)
    @guarded
    def login(body: LoginRequest,request: Request,response: Response):
        token,ttl,identity=store.login(body.username,body.password.get_secret_value(),request.client.host if request.client else 'unknown')
        request.state.principal=identity
        response.headers['Cache-Control']='no-store';response.headers['Pragma']='no-cache'
        return {'access_token':token,'expires_in':ttl,'principal':principal_info(identity)}

    @router.post('/api/auth/logout',response_model=LogoutResponse)
    @guarded
    def logout(request: Request,identity=Depends(principal)):
        token=request.headers.get('authorization','')[7:]
        if not token.startswith('sess_'):
            raise MinerUError('legacy_credential_requires_offline_revocation',409)
        store.logout(token)
        return {'revoked':True}

    @router.get('/api/admin/accounts',response_model=AccountPage)
    @guarded
    def listing(page: int=Query(1,ge=1),page_size: int=Query(20,ge=1,le=100),identity=Depends(require_admin)):
        value,_=store.load()
        return page_of([store.public(item) for item in value['accounts']],page,page_size,'private_auth_accounts')

    @router.get('/api/admin/account-events',response_model=AccountEventPage)
    @guarded
    def events(page: int=Query(1,ge=1),page_size: int=Query(20,ge=1,le=100),identity=Depends(require_admin)):
        value,_=store.load()
        return page_of(list(reversed(value['events'])),page,page_size,'private_auth_account_events')

    @router.post('/api/admin/accounts',status_code=201,response_model=AccountView)
    @guarded
    def create(body: AccountCreate,identity=Depends(require_admin)):
        def callback(value):
            if len(value['accounts'])>=1000:
                raise MinerUError('account_limit_reached',409)
            item={**body.model_dump(exclude={'password'}),'principal_id':'account-'+uuid4().hex,
                  'password_hash':hash_password(body.password.get_secret_value()),'credential_status':'active'}
            # 新账号生成自己的业务owner，不与历史local-user或QA owner自动关联。
            if item['owner_id'] is None and ('USER' in item['roles'] or 'ADMIN' in item['roles']):
                item['owner_id']=item['principal_id']
            value['accounts'].append(item)
            return item
        return store.change(identity.principal_id,'create',callback)

    @router.patch('/api/admin/accounts/{principal_id}',response_model=AccountView)
    @guarded
    def update(principal_id: str,body: AccountUpdate,identity=Depends(require_admin)):
        def callback(value):
            item=next((item for item in value['accounts'] if item['principal_id']==principal_id),None)
            if item is None:
                raise MinerUError('account_not_found',404)
            for key,entry in body.model_dump(exclude_unset=True,exclude={'password'}).items():
                if entry is None:
                    raise MinerUError('invalid_account_update',422)
                item[key]=entry
            if body.password is not None:
                item['password_hash']=hash_password(body.password.get_secret_value())
            return item
        return store.change(identity.principal_id,'update',callback)

    app.include_router(router)
