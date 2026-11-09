"""官方测试专用CONNECT入口；内核出站限制和最小权限缺失时禁止监听。"""
import argparse
import asyncio
import ipaddress
import json
import os
from pathlib import Path
import socket

OFFICIAL_HOSTS = frozenset({'mineru.net', 'mineru.oss-cn-shanghai.aliyuncs.com', 'cdn-mineru.openxlab.org.cn'})


def connect_host(header):
    """只允许标准CONNECT、固定DNS主机和443；不接收URL或客户端自选IP。"""
    if len(header) > 8192 or not header.endswith(b'\r\n\r\n'):
        raise ValueError('请求头无效')
    text = header.decode('ascii')
    first, *lines = text.split('\r\n')
    parts = first.split(' ')
    if len(parts) != 3 or parts[0] != 'CONNECT' or parts[2] != 'HTTP/1.1':
        raise ValueError('仅允许CONNECT')
    target = parts[1]
    if target.count(':') != 1:
        raise ValueError('主机或端口无效')
    host, port = target.split(':')
    if host not in OFFICIAL_HOSTS or port != '443':
        raise ValueError('目标不在固定官方范围')
    seen = set()
    for line in lines:
        if not line:
            continue
        if line[0].isspace() or ':' not in line:
            raise ValueError('请求头格式无效')
        key, value = line.split(':', 1)
        key = key.lower()
        if key in seen or key not in {'host', 'proxy-connection'}:
            raise ValueError('请求头不允许')
        seen.add(key)
        if key == 'host' and value.strip() != target:
            raise ValueError('Host不匹配')
    return host


def validate_pins(value):
    """启动前可信解析后的固定公网IP；代理运行期不提供通用DNS。"""
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ValueError('固定地址配置无效')
    hosts = value.get('hosts')
    if not isinstance(hosts, dict) or set(hosts) != OFFICIAL_HOSTS:
        raise ValueError('固定主机集合不符')
    result = {}
    for host, values in hosts.items():
        if not isinstance(values, list) or not values:
            raise ValueError('缺少已审核公网地址')
        parsed = [ipaddress.ip_address(value) for value in values]
        if any(not value.is_global for value in parsed):
            raise ValueError('禁止非公网解析地址')
        result[host] = tuple(str(value) for value in parsed)
    return result


def runtime_guard(attestation, pins):
    """受信init须先加载双栈规则再降权；不凭环境变量自行宣称隔离成功。"""
    if os.name != 'posix' or os.geteuid() == 0:
        raise ValueError('必须Linux非root')
    status = Path('/proc/self/status').read_text()
    cap = next(line.split(':', 1)[1].strip() for line in status.splitlines() if line.startswith('CapEff:'))
    if int(cap, 16) != 0:
        raise ValueError('运行期capabilities必须为零')
    info = attestation.stat()
    if info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('内核证明须root持有且非受信用户不可写')
    record = json.loads(attestation.read_text('utf-8'))
    if (record.get('network_namespace') != os.readlink('/proc/self/ns/net') or
            record.get('ipv4_default_drop') is not True or record.get('ipv6_default_drop') is not True or
            record.get('dns_after_init') is not False or record.get('allowed_hosts') != sorted(OFFICIAL_HOSTS) or
            record.get('allowed_addresses') != sorted({value for values in pins.values() for value in values}) or
            record.get('allowed_new_tcp_ports') != [443]):
        raise ValueError('内核证明与当前命名空间或固定范围不符')


async def serve(pins, client_ip):
    async def handle(reader, writer):
        upstream = None
        try:
            peer = writer.get_extra_info('peername')
            if not peer or peer[0] != client_ip:
                raise ValueError('非指定测试客户端')
            raw = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), timeout=10)
            host = connect_host(raw)
            for address in pins[host]:
                try:
                    family = socket.AF_INET6 if ':' in address else socket.AF_INET
                    incoming, upstream = await asyncio.wait_for(asyncio.open_connection(address, 443,
                        family=family, flags=socket.AI_NUMERICHOST), timeout=10)
                    break
                except (OSError, asyncio.TimeoutError):
                    pass
            if upstream is None:
                raise OSError('固定官方地址不可达')
            writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            await writer.drain()
            async def copy(source, target):
                while block := await asyncio.wait_for(source.read(65536), timeout=120):
                    target.write(block)
                    await target.drain()
            tasks = [asyncio.create_task(copy(reader, upstream)), asyncio.create_task(copy(incoming, writer))]
            _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            # 只返回固定状态，不打印CONNECT原文、异常URL或任何凭据。
            if upstream is None:
                writer.write(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
                await writer.drain()
        finally:
            if upstream:
                upstream.close()
            writer.close()
    server = await asyncio.start_server(handle, '0.0.0.0', 8080, limit=8192)
    async with server:
        await server.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pins', type=Path, required=True)
    parser.add_argument('--attestation', type=Path, required=True)
    parser.add_argument('--client-ip', required=True)
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args(argv)
    pins = validate_pins(json.loads(args.pins.read_text('utf-8')))
    ipaddress.ip_address(args.client_ip)
    runtime_guard(args.attestation, pins)
    if args.serve:
        asyncio.run(serve(pins, args.client_ip))
    else:
        print(json.dumps(dict(status='GUARD_PASS',listening=False,official_hosts=sorted(OFFICIAL_HOSTS))))


if __name__ == '__main__':
    main()
