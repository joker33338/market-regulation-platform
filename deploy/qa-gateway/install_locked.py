"""仅新增已锁定的nft闭包，不升级基础镜像已有包。"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def installed():
    return [dict(zip(('package', 'version', 'architecture'), line.split())) for line in
            run('dpkg-query', '-W', '-f=${Package} ${Version} ${Architecture}\n').splitlines()]


lock = json.loads(Path('/opt/qa/package-lock.json').read_text())
before = installed()
if before != lock['baseline_packages']:
    raise RuntimeError('基础镜像包清单与锁不匹配')
run('apt-get', 'update')
directory = Path('/tmp/qa-debs')
directory.mkdir()
for item in lock['new_packages']:
    subprocess.run(['apt-get', 'download', item['package'] + '=' + item['version']], cwd=directory, check=True)
for path in directory.glob('*.deb'):
    name = run('dpkg-deb', '-f', str(path), 'Package').strip()
    item = next(value for value in lock['new_packages'] if value['package'] == name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256'] or path.stat().st_size != int(item['size']):
        raise RuntimeError('下载包哈希或长度不符')
    if run('dpkg-deb', '-f', str(path), 'Version').strip() != item['version']:
        raise RuntimeError('包版本不符')
if len(list(directory.glob('*.deb'))) != len(lock['new_packages']):
    raise RuntimeError('依赖闭包缺失')
run('dpkg', '-i', *(str(path) for path in sorted(directory.glob('*.deb'))))
after = installed()
expected = sorted(before + [{key: item[key] for key in ('package', 'version', 'architecture')}
                            for item in lock['new_packages']], key=lambda item: item['package'])
if after != expected:
    raise RuntimeError('安装修改了锁定闭包之外的包')
run('dpkg', '--audit')
Path('/opt/qa/dpkg-installed.json').write_text(json.dumps(after, indent=2))
shutil.rmtree(directory)
shutil.rmtree('/var/lib/apt/lists')
