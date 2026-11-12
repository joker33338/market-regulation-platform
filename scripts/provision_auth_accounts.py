"""本机交互创建首个管理员；无默认密码、不接受命令行密码、不覆盖既有账号文件。"""
import argparse
from datetime import datetime,timezone
import getpass
import json
from pathlib import Path
import re
import subprocess
from uuid import uuid4

from filelock import FileLock
from qa_core.api.accounts import AccountStore,atomic_json,hash_password


def provision(path,username,password):
    path=Path(path)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]{2,63}',username) or not 12<=len(password)<=256:
        raise ValueError('账号格式无效或密码长度不符合要求')
    path.parent.mkdir(parents=True,exist_ok=True)
    if any((parent/'.git').exists() for parent in path.resolve().parents):
        try:
            ignored=subprocess.run(['git','-C',str(path.parent),'check-ignore','--quiet','--',str(path.resolve())],capture_output=True)
        except OSError:
            raise ValueError('无法核验Git忽略规则，停止初始化') from None
        if ignored.returncode!=0:
            raise ValueError('账号文件必须位于Git忽略的私密目录')
    with FileLock(str(path)+'.lock',timeout=3):
        if path.exists():
            raise ValueError('账号文件已存在，拒绝覆盖')
        principal_id='account-'+uuid4().hex
        account={'username':username,'password_hash':hash_password(password),'principal_id':principal_id,
                 'owner_id':principal_id,'roles':['ADMIN'],'review_owner_scopes':[],
                 'credential_status':'active','document_delete_owner_scopes':[]}
        value={'schema_version':1,'accounts':[account],'events':[{
            'event_id':uuid4().hex,'timestamp':datetime.now(timezone.utc).isoformat(),'operator_id':principal_id,
            'target_id':principal_id,'action':'bootstrap','roles':['ADMIN'],'credential_status':'active'}]}
        AccountStore(path.parent).validate_value(value)
        atomic_json(path,value)
        return principal_id


def main():
    parser=argparse.ArgumentParser(description='仅在获准的私密本机目录初始化管理员账号')
    parser.add_argument('--output',required=True)
    parser.add_argument('--username',required=True)
    args=parser.parse_args()
    password=getpass.getpass('管理员密码（至少12位，不回显）：')
    confirmation=getpass.getpass('再次输入密码：')
    if password!=confirmation:
        raise SystemExit('两次密码不一致，未创建账号')
    try:
        principal_id=provision(args.output,args.username,password)
    except (ValueError,OSError):
        raise SystemExit('初始化失败；核查目标是否已存在及本机私密目录权限') from None
    print(json.dumps({'created':True,'principal_id':principal_id,'role':'ADMIN'}))


if __name__=='__main__':
    main()
