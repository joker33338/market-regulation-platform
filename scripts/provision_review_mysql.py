"""显式初始化全新审核库；禁止改动已有库，API运行账号不具备DDL权限。"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys


def main():
    import pymysql
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--config-out', required=True, type=Path)
    parser.add_argument('--writer', action='append', default=[])
    parser.add_argument('--api-host', required=True)
    parser.add_argument('--api-port', type=int, default=3306)
    args=parser.parse_args()
    if not re.fullmatch(r'market_review(?:_test_[a-f0-9]+)?',args.database):
        parser.error('只允许独立审核库或隔离测试库名称')
    root=Path(__file__).resolve().parents[1]
    target=args.config_out.resolve()
    if not target.is_relative_to((root/'local').resolve()) or target.exists():
        parser.error('配置只能新建在本仓库ignored local内，不能覆盖已有文件')
    admin=json.loads(os.environ['REVIEW_MYSQL_ADMIN_JSON'])
    # 不打印管理员配置、SQL或底层异常；部分DDL失败时保留现场，禁止自动清库。
    connection=pymysql.connect(**admin,charset='utf8mb4',connect_timeout=5)
    user='review_api_'+secrets.token_hex(6)
    password=secrets.token_hex(32)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s',(args.database,))
            if cursor.fetchone():
                raise RuntimeError('审核库已存在，不执行任何变更')
            cursor.execute(f'CREATE DATABASE `{args.database}` CHARACTER SET utf8mb4')
            connection.select_db(args.database)
            sql=(root/'qa_core/storage/review_ledger.sql').read_text(encoding='utf-8')
            for statement in sql.split(';'):
                if statement.strip():
                    cursor.execute(statement)
            cursor.execute('CREATE USER %s@%s IDENTIFIED BY %s',(user,'%',password))
            for permissions,table in [('SELECT','review_meta'),('SELECT,INSERT,UPDATE','review_heads'),('SELECT,INSERT','review_events')]:
                cursor.execute(f'GRANT {permissions} ON `{args.database}`.`{table}` TO %s@%s',(user,'%'))
        connection.commit()
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('x',encoding='utf-8') as stream:
            json.dump(dict(host=args.api_host,port=args.api_port,user=user,password=password,
                           database=args.database,writers=args.writer),stream)
        print('新审核库与最小权限账号准备完成；配置仅保存在指定ignored文件。')
    finally:
        connection.close()


if __name__=='__main__':
    try:
        main()
    except Exception:
        print('初始化未完成，请在本机核实配置及权限；保留现场，不输出凭据。',file=sys.stderr)
        raise SystemExit(1)
