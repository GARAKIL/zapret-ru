import unittest

from core.engine import (
    EngineConfig,
    domain_allowed,
    extract_host,
    normalize_host,
    parse_http_host,
    parse_tls_client_hello,
    split_position,
)


def make_client_hello(host: str) -> bytes:
    name = host.encode("idna")
    server_name = b"\x00" + len(name).to_bytes(2, "big") + name
    name_list = len(server_name).to_bytes(2, "big") + server_name
    sni_ext = b"\x00\x00" + len(name_list).to_bytes(2, "big") + name_list
    body = (
        b"\x03\x03"
        + bytes(range(32))
        + b"\x00"
        + b"\x00\x02\x13\x01"
        + b"\x01\x00"
        + len(sni_ext).to_bytes(2, "big")
        + sni_ext
    )
    handshake = b"\x01" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x01" + len(handshake).to_bytes(2, "big") + handshake


class TlsParserTests(unittest.TestCase):
    def test_extracts_sni_range(self):
        payload = make_client_hello("www.youtube.com")
        info = parse_tls_client_hello(payload)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.host, "www.youtube.com")
        self.assertEqual(
            payload[info.start : info.start + info.length], b"www.youtube.com"
        )

    def test_ignores_non_tls(self):
        self.assertIsNone(parse_tls_client_hello(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n"))
        self.assertIsNone(parse_tls_client_hello(b"\x16\x03\x01\x00"))

    def test_split_inside_sni(self):
        payload = make_client_hello("discord.com")
        info = parse_tls_client_hello(payload)
        assert info is not None
        position = split_position(payload, info, "sni")
        self.assertGreater(position, info.start)
        self.assertLess(position, info.start + info.length)
        self.assertLess(position, len(payload))

    def test_fixed_split_is_clamped(self):
        payload = make_client_hello("cloudflare.com")
        self.assertEqual(split_position(payload, None, 10000), len(payload) - 1)
        self.assertEqual(split_position(payload, None, 1), 1)


class HttpParserTests(unittest.TestCase):
    def test_host_header(self):
        payload = b"GET / HTTP/1.1\r\nHost: example.com:443\r\nUser-Agent: x\r\n\r\n"
        info = parse_http_host(payload)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.host, "example.com")
        self.assertEqual(
            payload[info.start : info.start + info.length], b"example.com:443"
        )

    def test_rejects_fake_host_in_body(self):
        payload = b"POST / HTTP/1.1\r\nContent-Length: 5\r\n\r\nhost: bad"
        self.assertIsNone(parse_http_host(payload))

    def test_extract_selects_tls_or_http(self):
        tls = make_client_hello("example.com")
        self.assertEqual(extract_host(tls).kind, "tls")
        http = b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n"
        self.assertEqual(extract_host(http).kind, "http")


class DomainPolicyTests(unittest.TestCase):
    def config(self, mode="list", include=(), exclude=()):
        return EngineConfig(
            profile_id="test",
            profile_name="Test",
            split="sni",
            block_quic=True,
            mode=mode,
            include=frozenset(include),
            exclude=frozenset(exclude),
        )

    def test_list_mode(self):
        config = self.config(include=("youtube.com",))
        self.assertTrue(domain_allowed("www.youtube.com", config))
        self.assertFalse(domain_allowed("example.org", config))

    def test_global_mode_and_exclusions(self):
        config = self.config(mode="global", exclude=("gosuslugi.ru",))
        self.assertTrue(domain_allowed("youtube.com", config))
        self.assertFalse(domain_allowed("www.gosuslugi.ru", config))

    def test_wildcard(self):
        config = self.config(include=("*.example.com",))
        self.assertTrue(domain_allowed("a.example.com", config))
        self.assertTrue(domain_allowed("example.com", config))
        self.assertFalse(domain_allowed("badexample.com", config))

    def test_normalize(self):
        self.assertEqual(normalize_host("WWW.Example.COM."), "www.example.com")
        self.assertEqual(normalize_host("example.com:443"), "example.com")


if __name__ == "__main__":
    unittest.main()
