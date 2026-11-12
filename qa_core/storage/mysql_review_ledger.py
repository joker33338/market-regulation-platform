"""独立MySQL审核台账；运行时只执行DML，不修改OCR、PostgreSQL或发布状态。"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from uuid import uuid4

from qa_core.document_parsing.mineru_client import MinerUError


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class MySQLReviewLedger:
    def __init__(self, config):
        import re
        if not re.fullmatch(r'market_review(?:_test_[a-f0-9]+)?', config.get('database', '')):
            raise ValueError('审核台账必须使用独立数据库')
        if config.get('user', '').lower() == 'root':
            raise ValueError('审核服务禁止使用root')
        # 旧writers键仅兼容读取；不再参与身份或审核授权。
        self.config = {key: config[key] for key in ('host', 'port', 'user', 'password', 'database')}

    @classmethod
    def from_env(cls):
        value = os.getenv('REVIEW_MYSQL_CONFIG_JSON')
        return cls(json.loads(value)) if value else None

    @contextmanager
    def connection(self):
        import pymysql
        connection = pymysql.connect(**self.config, charset='utf8mb4', autocommit=False,
            connect_timeout=5, read_timeout=10, write_timeout=10, local_infile=False,
            cursorclass=pymysql.cursors.DictCursor)
        try:
            yield connection
            connection.commit()
        except pymysql.IntegrityError:
            connection.rollback()
            raise MinerUError('review_integrity_conflict', 409) from None
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def health(self):
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT schema_version FROM review_meta WHERE singleton=1')
            if cursor.fetchone() != {'schema_version': 1}:
                raise MinerUError('review_ledger_schema_mismatch', 503)

    def state(self, owner, parse_id):
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT version,status,current_revision FROM review_heads WHERE owner_key=%s AND parse_id=%s',
                           (digest(owner), parse_id))
            return cursor.fetchone() or {'version': 0, 'status': 'unreviewed', 'current_revision': None}

    def verify_for_ingestion(self, owner, parse_id, source_digest, expected_version):
        with self.connection() as connection,connection.cursor() as cursor:
            cursor.execute('SELECT version,status,current_revision,source_digest FROM review_heads WHERE owner_key=%s AND parse_id=%s',
                           (digest(owner),parse_id))
            value=cursor.fetchone()
            if not value or value['status']!='approved' or value['version']!=expected_version or value['source_digest']!=source_digest:
                raise MinerUError('review_approval_required',409)
            return value

    @contextmanager
    def verified_ingestion_scope(self, references):
        with self.connection() as connection,connection.cursor() as cursor:
            for reference in sorted(references,key=lambda value:(digest(value['owner_id']),value['parse_id'])):
                cursor.execute('SELECT version,status,current_revision,source_digest FROM review_heads WHERE owner_key=%s AND parse_id=%s FOR SHARE',
                               (digest(reference['owner_id']),reference['parse_id']))
                value=cursor.fetchone()
                if (not value or value['status']!='approved' or value['version']!=reference['version']
                        or value['source_digest']!=reference['source_digest'] or value['current_revision']):
                    raise MinerUError('review_approval_required',409)
            yield

    def events(self, owner, parse_id, page, page_size):
        with self.connection() as connection, connection.cursor() as cursor:
            args = (digest(owner), parse_id)
            cursor.execute('SELECT count(*) AS total FROM review_events WHERE owner_key=%s AND parse_id=%s', args)
            total = cursor.fetchone()['total']
            cursor.execute('SELECT receipt,payload FROM review_events WHERE owner_key=%s AND parse_id=%s ORDER BY version DESC LIMIT %s OFFSET %s',
                           (*args, page_size, (page-1)*page_size))
            rows = [{**json.loads(row['receipt']), 'request': json.loads(row['payload'])} for row in cursor.fetchall()]
            return {'list': rows, 'total': total, 'page': page, 'page_size': page_size, 'source': 'mysql.review_events'}

    def audit_logs(self, owner, page, page_size, action=None):
        from qa_core.access import is_all_owners
        global_scope=is_all_owners(owner)
        owners = [] if global_scope else [owner] if isinstance(owner,str) else list(owner)
        if not owners and not global_scope:
            return {'list': [], 'total': 0, 'page': page, 'page_size': page_size, 'source': 'mysql.review_events'}
        where = 'TRUE' if global_scope else 'owner_key IN ('+','.join(['%s']*len(owners))+')'
        args = [digest(value) for value in owners]
        if action is not None:
            where += " AND JSON_UNQUOTE(JSON_EXTRACT(receipt,'$.action'))=%s"
            args.append(action)
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT count(*) AS total FROM review_events WHERE '+where, args)
            total = cursor.fetchone()['total']
            cursor.execute("SELECT receipt FROM review_events WHERE "+where+
                " ORDER BY JSON_UNQUOTE(JSON_EXTRACT(receipt,'$.timestamp')) DESC,event_id DESC LIMIT %s OFFSET %s",
                [*args,page_size,(page-1)*page_size])
            rows = [json.loads(row['receipt']) for row in cursor.fetchall()]
        return {'list': rows, 'total': total, 'page': page, 'page_size': page_size, 'source': 'mysql.review_events'}

    def apply(self, owner, parse_id, action, body, request_key, source_digest, *, operator_id):
        if not operator_id:
            raise MinerUError('principal_required',403)
        owner_key, key_hash = digest(owner), digest(canonical({'principal_id':operator_id,'key':request_key}))
        fingerprint = digest(canonical({'parse_id': parse_id, 'action': action, 'body': body}))
        with self.connection() as connection, connection.cursor() as cursor:
            # 同一对象先锁头记录，串行化版本分配；事件与头记录在同一事务提交。
            cursor.execute('INSERT INTO review_heads(owner_key,parse_id,version,status,source_digest) VALUES(%s,%s,0,%s,%s) ON DUPLICATE KEY UPDATE owner_key=owner_key',
                           (owner_key, parse_id, 'unreviewed', source_digest))
            cursor.execute('SELECT version,status,current_revision,source_digest FROM review_heads WHERE owner_key=%s AND parse_id=%s FOR UPDATE',
                           (owner_key, parse_id))
            head = cursor.fetchone()
            cursor.execute('SELECT fingerprint,receipt FROM review_events WHERE owner_key=%s AND request_key=%s', (owner_key,key_hash))
            existing = cursor.fetchone()
            if existing:
                if existing['fingerprint'] != fingerprint:
                    raise MinerUError('idempotency_conflict', 409)
                return json.loads(existing['receipt'])
            if head['source_digest'] != source_digest:
                raise MinerUError('review_source_changed', 409)
            if head['version'] != body['expected_version']:
                raise MinerUError('review_version_conflict', 409)
            revision = str(uuid4()) if action == 'save-revision' else head['current_revision']
            status = {'approve': 'approved', 'reject': 'rejected', 'mark-error': 'flagged', 'save-revision': 'pending'}[action]
            receipt = {'event_id': str(uuid4()), 'parse_id': parse_id, 'base_result_id': parse_id,
                       'action': action, 'operator': operator_id, 'operator_id': operator_id, 'owner_id': owner,
                       'identity_model':'principal-v1', 'timestamp': datetime.now(timezone.utc).isoformat(),
                       'version': head['version']+1, 'revision_id': revision, 'status': status,
                       'before': {'version': head['version'], 'status': head['status'], 'revision_id': head['current_revision']},
                       'write_performed': True, 'original_result_modified': False,
                       'publish_authorized': False, 'reparse_task_created': False}
            cursor.execute('INSERT INTO review_events(event_id,owner_key,parse_id,version,request_key,fingerprint,receipt,payload) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                           (receipt['event_id'],owner_key,parse_id,receipt['version'],key_hash,fingerprint,canonical(receipt),canonical(body)))
            cursor.execute('UPDATE review_heads SET version=%s,status=%s,current_revision=%s WHERE owner_key=%s AND parse_id=%s',
                           (receipt['version'],status,revision,owner_key,parse_id))
            return receipt
