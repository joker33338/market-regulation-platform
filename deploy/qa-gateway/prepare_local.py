"""仅在Git忽略目录准备匿名Mock配置与冻结源码，不接触原始项目工作树。"""
import argparse
import hashlib
import io
import ipaddress
import json
from pathlib import Path
import secrets
import subprocess
import tarfile

SOURCE = '67709c4989781594dd6c4723666fdb2c21caaa7b'
BASE = 'sha256:b4010953b65e06c2d1000fdcd129f6fcceeed9b9a5d48a12266d3365a610a2b1'


def run(*args):
    return subprocess.run(args, check=True, capture_output=True).stdout


def check_networks(host_routes=None):
    names = run('docker', 'network', 'ls', '--format', '{{.Name}}').decode().splitlines()
    records = json.loads(run('docker', 'network', 'inspect', *names))
    wanted = [ipaddress.ip_network(f'172.30.{value}.0/28') for value in (250, 251, 252)]
    if host_routes:
        for prefix in json.loads(host_routes.read_text(encoding='utf-8-sig')):
            network = ipaddress.ip_network(prefix)
            if network.prefixlen and not network.is_multicast and any(network.overlaps(value) for value in wanted):
                raise RuntimeError('候选独立网段与宿主路由重叠')
    for record in records:
        own = record.get('Labels', {}).get('com.docker.compose.project') == 'market-regulation-qa-localhost'
        for config in record.get('IPAM', {}).get('Config') or []:
            if config.get('Subnet'):
                network = ipaddress.ip_network(config['Subnet'])
                if not own and network.version == 4 and any(network.overlaps(value) for value in wanted):
                    raise RuntimeError('候选独立网段与已有网络重叠')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--host-routes', type=Path)
    args = parser.parse_args()
    check_networks(args.host_routes)
    base = json.loads(run('docker', 'image', 'inspect', BASE))[0]
    if base['Id'] != BASE:
        raise RuntimeError('基础镜像身份不符')
    if args.check_only:
        print('网络与基础镜像检查通过')
        return
    root = args.root.resolve()
    repo = Path(__file__).resolve().parents[2]
    if not root.is_relative_to(repo / 'local'):
        raise RuntimeError('配置只能位于当前工作树Git忽略local目录')
    root.mkdir(parents=True, exist_ok=True)
    run('git', 'check-ignore', str(root))
    source = root / 'source'
    if source.exists():
        if (root / 'source.commit').read_text().strip() != SOURCE:
            raise RuntimeError('已有快照版本不符，不覆盖')
    else:
        payload = run('git', 'archive', SOURCE, 'qa_core', 'scripts', 'tests', 'scenarios')
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as archive:
            archive.extractall(source, filter='data')
        (root / 'source.commit').write_text(SOURCE + '\n')
    # 每次核验所有业务Python，不把原始资料或凭据复制进快照。
    files = run('git', 'ls-tree', '-r', '--name-only', SOURCE, 'qa_core').decode().splitlines()
    for name in files:
        if name.endswith('.py') and ((source / name).read_bytes().replace(b'\r\n', b'\n') !=
                                    run('git', 'show', SOURCE + ':' + name).replace(b'\r\n', b'\n')):
            raise RuntimeError('业务源码快照不符')
    for name in ('state', 'output'):
        (root / name).mkdir(exist_ok=True)
    runtime = root / 'runtime.json'
    if not runtime.exists():
        runtime.write_text(json.dumps(dict(PARSING_API_TOKENS_JSON=json.dumps({secrets.token_hex(32): 'local-qa'}),
                          MINERU_ENABLED='1', MINERU_MODE='mock', MINERU_PROVIDER='self_hosted',
                          DUAL_OCR_ENABLED='0', DUAL_OCR_CLOUD_ENABLED='0'), indent=2), encoding='utf-8')
    print('匿名Mock本地配置与冻结源码已准备，未输出凭据')


if __name__ == '__main__':
    main()
