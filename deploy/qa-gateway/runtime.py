"""降权后的固定角色，权限检查通过前不加载应用配置或开始监听。"""
import asyncio
import json
import os
from pathlib import Path
import sys
import time


def guard():
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    if (os.getuid() == 0 or os.geteuid() == 0 or status['NoNewPrivs'].strip() != '1' or
            any(int(status[key].strip(), 16) != 0 for key in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'))):
        raise RuntimeError('运行期权限未清零')
    for name in ('kernel-attestation.json', 'client-kernel-attestation.json'):
        path = Path('/policy') / name
        if path.exists():
            info = path.stat()
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise RuntimeError('证明可被非受信用户修改')
            if json.loads(path.read_text())['network_namespace'] != os.readlink('/proc/self/ns/net'):
                raise RuntimeError('证明命名空间不符')


def main():
    guard()
    role = sys.argv[1]
    print(json.dumps(dict(status='KERNEL_GUARD_PASS', role=role, uid=os.getuid(), capabilities=0)), flush=True)
    if role == 'tls-egress':
        from qa_mineru_egress_proxy import runtime_guard, serve, validate_pins
        value = json.loads(Path('/policy/pins.json').read_text())
        pins = validate_pins(value)
        runtime_guard(Path('/policy/kernel-attestation.json'), pins)
        seconds = value['expires_at'] - time.time()
        if seconds <= 0:
            raise RuntimeError('固定地址已过期')
        async def bounded():
            try:
                await asyncio.wait_for(serve(pins, '172.30.250.10'), timeout=seconds)
            except asyncio.TimeoutError:
                # 到期正常停止，不由restart策略自动刷新已批准窗口。
                print('{"status":"PINS_EXPIRED"}', flush=True)
        asyncio.run(bounded())
    elif role == 'local-ingress':
        from fixed_proxy import serve
        asyncio.run(serve())
    elif role == 'client':
        # 仅提供已隔离的空闲进程；QA通过stdin提供Key，不放Docker环境或镜像。
        while True:
            time.sleep(60)
    elif role == 'app':
        # 私密配置只由已清零权限的应用进程读取，不能配置任意启动命令或数据库。
        path = Path('/private/runtime.json')
        values = json.loads(path.read_text('utf-8'))
        allowed = {'PARSING_API_TOKENS_JSON', 'MINERU_ENABLED', 'MINERU_MODE', 'MINERU_PROVIDER',
                   'MINERU_RESULT_DIR', 'MINERU_API_KEY', 'DUAL_OCR_ENABLED', 'DUAL_OCR_CLOUD_ENABLED',
                   'DUAL_OCR_ENVIRONMENT', 'DUAL_OCR_AUTHORIZATION_MODE', 'DUAL_OCR_TEST_BATCH_MANIFEST',
                   'DUAL_OCR_TEST_BATCH_OWNER', 'DUAL_OCR_TEST_BATCH_ID'}
        if set(values) - allowed or not all(isinstance(value, str) for value in values.values()):
            raise RuntimeError('应用本地配置包含不允许字段')
        os.environ.update(values)
        os.environ['MINERU_RESULT_DIR'] = '/state/results'
        os.environ['PYTHONPATH'] = '/source'
        os.chdir('/source')
        os.execvp('python', ['python', '-B', '-m', 'uvicorn', 'qa_core.document_parsing.mineru_api:create_app',
                            '--factory', '--host', '0.0.0.0', '--port', '8180', '--workers', '1',
                            '--log-level', 'warning', '--no-access-log'])


if __name__ == '__main__':
    main()
