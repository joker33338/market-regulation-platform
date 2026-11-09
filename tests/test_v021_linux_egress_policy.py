"""只测试代理的纯函数边界，不创建监听、解析DNS或访问外部服务。"""
import unittest
from tests.qa_mineru_egress_proxy import OFFICIAL_HOSTS, connect_host, validate_pins


def request(target, method='CONNECT', extra=''):
    return f'{method} {target} HTTP/1.1\r\nHost: {target}\r\n{extra}\r\n'.encode('ascii')


class EgressPolicyContract(unittest.TestCase):
    def test_three_exact_hosts_are_accepted(self):
        for host in OFFICIAL_HOSTS:
            self.assertEqual(connect_host(request(host+':443')), host)

    def test_external_hosts_and_suffix_tricks_are_rejected(self):
        for host in ('www.google.com', 'mineru.net.attacker.invalid', 'mineru.net.', 'MINERU.NET'):
            with self.assertRaises(ValueError):
                connect_host(request(host+':443'))

    def test_ip_literals_and_other_ports_are_rejected(self):
        for target in ('8.8.8.8:443', '[2606:4700:4700::1111]:443', 'mineru.net:80', 'mineru.net:0443'):
            with self.assertRaises(ValueError):
                connect_host(request(target))

    def test_urls_userinfo_and_paths_are_rejected(self):
        for target in ('https://mineru.net:443', 'user@mineru.net:443', 'mineru.net:443/path'):
            with self.assertRaises(ValueError):
                connect_host(request(target))

    def test_plain_http_and_connect_ambiguous_headers_are_rejected(self):
        for raw in (request('mineru.net:443',method='GET'),
                    request('mineru.net:443',extra='Host: other.invalid:443\r\n'),
                    request('mineru.net:443',extra='Authorization: secret\r\n')):
            with self.assertRaises(ValueError):
                connect_host(raw)

    def test_private_loopback_linklocal_ipv6_destinations_are_rejected(self):
        for address in ('127.0.0.1','10.0.0.1','169.254.169.254','::1','fd00::1','fe80::1'):
            with self.assertRaises(ValueError):
                validate_pins(dict(version=1,hosts={host:[address] for host in OFFICIAL_HOSTS}))

    def test_pin_sets_must_match_all_official_hosts(self):
        with self.assertRaises(ValueError):
            validate_pins(dict(version=1,hosts={'mineru.net':['8.8.8.8']}))
        with self.assertRaises(ValueError):
            validate_pins(dict(version=1,hosts={host:[] for host in OFFICIAL_HOSTS}))

    def test_reviewed_public_ipv4_ipv6_pins_are_retained(self):
        hosts={host:['8.8.8.8','2606:4700:4700::1111'] for host in OFFICIAL_HOSTS}
        self.assertEqual(set(validate_pins(dict(version=1,hosts=hosts))),OFFICIAL_HOSTS)


if __name__ == '__main__':
    unittest.main()
