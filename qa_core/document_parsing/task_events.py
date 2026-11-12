"""从实际持久化状态变化记录事件；不回填历史阶段或推断百分比。"""
from datetime import datetime, timezone
import re
from uuid import uuid4


def snapshot(task):
    def token(value):
        return value if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',value) else None
    return {'status':token(task.get('status')) or 'unknown',
            'files':[{'file_id':item['id'],'status':token(item.get('status')) or 'unknown',
                      'error_code':token((item.get('error') or {}).get('code')) if isinstance(item.get('error'),dict) else None}
                     for item in task.get('files',[])]}


def append_events(task, previous=None):
    before=snapshot(previous) if previous else None
    after=snapshot(task)
    events=list((previous or {}).get('stage_events',[]))
    if after!=before:
        events.append({'event_id':uuid4().hex,'timestamp':datetime.now(timezone.utc).isoformat(),
                       'kind':'task_created' if previous is None else 'state_changed',**after})
    task['stage_events']=events[-2000:]
    task['stage_events_truncated']=len(events)>2000 or bool((previous or {}).get('stage_events_truncated'))
    task['stage_events_started_at']=(previous or {}).get('stage_events_started_at') or (events[0]['timestamp'] if events else None)
