"""引擎加载失败的最小安全诊断，不传播异常原文或本机路径。"""
from qa_core.utils import IngestionError


_COMPONENTS = {'paddle', 'mineru_transport'}
_REASONS = {'WINDOWS_POLICY_BLOCKED', 'LOCAL_DEPENDENCY_ERROR'}
_EXCEPTIONS = {'ImportError', 'ModuleNotFoundError', 'OSError', 'PermissionError',
               'FileNotFoundError', 'IngestionError', 'Exception'}


def engine_unavailable(exc, *, component):
    """仅结构化系统错误码能证明策略拒绝，消息文本不作为证据。"""
    if component not in _COMPONENTS:
        raise ValueError('未知引擎组件')
    pending, seen, policy = [exc], set(), False
    while pending and len(seen) < 32:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        code = getattr(current, 'winerror', None)
        if type(code) is int and code in {577, 1260}:
            policy = True
        pending.extend(item for item in (getattr(current, '__cause__', None),
                                         getattr(current, '__context__', None)) if isinstance(item, BaseException))
    name = type(exc).__name__
    return dict(status='LOCAL_ENGINE_UNAVAILABLE',
                reason='WINDOWS_POLICY_BLOCKED' if policy else 'LOCAL_DEPENDENCY_ERROR',
                exception_type=name if name in _EXCEPTIONS else 'Exception', component=component)


def safe_diagnostic(value):
    """跨进程或候选中的附件仅保留四个受控字段。"""
    if (not isinstance(value, dict) or value.get('status') != 'LOCAL_ENGINE_UNAVAILABLE'
            or not isinstance(value.get('reason'), str) or value['reason'] not in _REASONS
            or not isinstance(value.get('component'), str) or value['component'] not in _COMPONENTS):
        return None
    name = value.get('exception_type')
    return dict(status='LOCAL_ENGINE_UNAVAILABLE', reason=value['reason'], component=value['component'],
                exception_type=name if isinstance(name, str) and name in _EXCEPTIONS else 'Exception')


def attached_diagnostic(exc, *, component):
    """通用算法异常不标记为依赖不可用；已附诊断仍需正规化。"""
    value = safe_diagnostic(getattr(exc, 'diagnostic', None))
    if value and value['component'] == component:
        return value
    if isinstance(exc, (ImportError, OSError)):
        return engine_unavailable(exc, component=component)
    return None
