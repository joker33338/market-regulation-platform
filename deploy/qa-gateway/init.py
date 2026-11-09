"""无私密配置的可信初始化：先内核拒绝规则，再清空权限并执行服务。"""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import time

from qa_mineru_egress_proxy import OFFICIAL_HOSTS, validate_pins

APP = '172.30.250.10'
TLS = '172.30.250.11'
INGRESS = '172.30.250.12'
POLICY = Path('/policy')


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout


def rules(role, pins):
    if role == 'local-ingress':
        incoming = 'tcp dport 8180 ct state { new, established } counter accept'
        outgoing = f'ip daddr {APP} tcp dport 8180 ct state {{ new, established }} counter accept'
    elif role in {'app', 'client'}:
        incoming = f'ip saddr {INGRESS} tcp dport 8180 ct state {{ new, established }} counter accept' if role == 'app' else ''
        outgoing = f'ip daddr {TLS} tcp dport 8080 ct state {{ new, established }} counter accept'
        if role == 'app':
            # 只允许固定应用自检，不放开Docker DNS或其它回环地址、端口。
            incoming += '\niifname "lo" ip saddr 127.0.0.1 ip daddr 127.0.0.1 tcp dport 8180 ct state { new, established } counter accept'
            outgoing += '\noifname "lo" ip saddr 127.0.0.1 ip daddr 127.0.0.1 tcp dport 8180 ct state { new, established } counter accept'
    else:
        incoming = f'ip saddr {APP} tcp dport 8080 ct state {{ new, established }} counter accept'
        outgoing = '\n'.join(f'{"ip6" if ":" in address else "ip"} daddr {address} tcp dport 443 '
                             'ct state { new, established } counter accept'
                             for address in sorted({value for values in pins.values() for value in values}))
    # -150在连接跟踪(-200)之后、Docker目的地址转换(-100)之前，DNS不能借DNAT绕过。
    return f'''table inet qa_guard {{
 chain input {{ type filter hook input priority -150; policy drop;
  ct state invalid counter drop
  ct direction reply ct state established counter accept
  {incoming}
  counter drop
 }}
 chain output {{ type filter hook output priority -150; policy drop;
  ct state invalid counter drop
  ct direction reply ct state established counter accept
  {outgoing}
  counter drop
 }}
 chain forward {{ type filter hook forward priority -150; policy drop; counter drop; }}
}}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=('local-ingress', 'app', 'client', 'tls-egress'))
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('初始化需独立命名空间最小权限')
    POLICY.mkdir(exist_ok=True)
    os.chmod(POLICY, 0o755)
    pins, expires = {}, None
    if args.role == 'tls-egress':
        # 只在无密钥初始化期解析固定三域；运行期禁止任何DNS。
        pins = {host: sorted({entry[4][0] for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
                for host in sorted(OFFICIAL_HOSTS)}
        pins = validate_pins(dict(version=1, hosts=pins))
        expires = time.time() + 1800
    text = rules(args.role, pins)
    existing = subprocess.run(['nft', 'list', 'table', 'inet', 'qa_guard'], capture_output=True).returncode == 0
    payload = ('delete table inet qa_guard\n' if existing else '') + text
    run('nft', '--check', '-f', '-', input=payload)
    run('nft', '-f', '-', input=payload)
    live = json.loads(run('nft', '-j', 'list', 'table', 'inet', 'qa_guard'))
    chains = [item['chain'] for item in live['nftables'] if 'chain' in item]
    if len(chains) != 3 or any(item.get('policy') != 'drop' or item.get('prio') != -150 for item in chains):
        raise RuntimeError('内核规则读回不符')
    for target in ('/proc/sys/net/ipv4/ip_forward', '/proc/sys/net/ipv6/conf/all/forwarding'):
        if Path(target).read_text().strip() != '0':
            raise RuntimeError('命名空间转发未关闭')
    record = dict(role=args.role, network_namespace=os.readlink('/proc/self/ns/net'),
                  ipv4_default_drop=True, ipv6_default_drop=True, dns_after_init=False,
                  allowed_hosts=sorted(OFFICIAL_HOSTS) if pins else [],
                  allowed_addresses=sorted({value for values in pins.values() for value in values}) if pins else
                                    [APP if args.role == 'local-ingress' else TLS],
                  allowed_new_tcp_ports=[443] if pins else [8180 if args.role == 'local-ingress' else 8080],
                  expires_at=expires, rule_sha256=hashlib.sha256(text.encode()).hexdigest())
    proof = 'client-kernel-attestation.json' if args.role in {'app', 'client'} else 'kernel-attestation.json'
    for name, value in ((proof, record), ('rules.json', live), ('pins.json', dict(version=1, hosts=pins, expires_at=expires))):
        path = POLICY / name
        path.write_text(json.dumps(value), encoding='utf-8')
        os.chmod(path, 0o444)
    # 初始化进程直接exec，不保留root父进程或可修改规则的服务通道。
    os.execvp('setpriv', ['setpriv', '--reuid=65534', '--regid=65534', '--clear-groups',
                         '--inh-caps=-all', '--ambient-caps=-all', '--bounding-set=-all', '--no-new-privs',
                         'python', '-B', '/opt/qa/runtime.py', args.role])


if __name__ == '__main__':
    main()
