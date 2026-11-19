"""Track C - Active padding audit of public encrypted-DNS resolvers (RQ3).

For every resolver we send the same set of queries over DoH (RFC 8484, POST,
HTTP/2) and DoT (RFC 7858), once WITHOUT a client EDNS(0) Padding option and
once WITH one (client pads queries to a 128-byte block, RFC 8467).  Because we
are the endpoint, we see the decrypted reply and can read the ground truth:

  * does the reply carry an EDNS(0) Padding option (RFC 7830)?
  * what is the reply's DNS-message length, and is it a multiple of 128 / 468?
  * does the resolver pad only when the client pads?

Only our own queries are sent (a few hundred in total), no third-party traffic
is observed.  Output: results/padding_audit_raw.csv and padding_audit_summary.csv
"""
import csv, os, socket, ssl, struct, sys, time
from collections import defaultdict

import dns.edns
import dns.message
import dns.rdatatype
import certifi
import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "results", "padding_audit")
os.makedirs(OUT, exist_ok=True)

RESOLVERS = [
    # name, DoH URL, DoT host (connect), DoT SNI
    ("Cloudflare", "https://1.1.1.1/dns-query", "1.1.1.1", "cloudflare-dns.com"),
    ("Google", "https://dns.google/dns-query", "8.8.8.8", "dns.google"),
    ("Quad9", "https://dns.quad9.net/dns-query", "9.9.9.9", "dns.quad9.net"),
    ("AdGuard", "https://dns.adguard-dns.com/dns-query", "dns.adguard-dns.com", "dns.adguard-dns.com"),
    ("OpenDNS", "https://doh.opendns.com/dns-query", "208.67.222.222", "dns.opendns.com"),
    ("NextDNS", "https://dns.nextdns.io/dns-query", "dns.nextdns.io", "dns.nextdns.io"),
    ("CleanBrowsing", "https://doh.cleanbrowsing.org/doh/security-filter/",
     "security-filter-dns.cleanbrowsing.org", "security-filter-dns.cleanbrowsing.org"),
    ("Mullvad", "https://dns.mullvad.net/dns-query", "dns.mullvad.net", "dns.mullvad.net"),
    ("DNS.SB", "https://doh.dns.sb/dns-query", "dot.sb", "dot.sb"),
    ("ControlD", "https://freedns.controld.com/p0", "p0.freedns.controld.com", "p0.freedns.controld.com"),
    ("AliDNS", "https://dns.alidns.com/dns-query", "dns.alidns.com", "dns.alidns.com"),
]

# Mix of short and long answers (CNAME chains, many A/AAAA records).
QUERIES = [
    ("google.com", "A"), ("youtube.com", "AAAA"), ("wikipedia.org", "A"),
    ("www.amazon.com", "A"), ("www.microsoft.com", "AAAA"), ("www.netflix.com", "A"),
    ("dawn.com", "A"), ("www.daraz.pk", "A"), ("www.nadra.gov.pk", "A"),
    ("cdn.jsdelivr.net", "A"), ("www.reddit.com", "AAAA"), ("github.com", "TXT"),
    ("gmail.com", "MX"), ("cloudflare.com", "TXT"), ("example.com", "A"),
    ("nonexistent-xq7z.example", "A"),
]


def build_query(name, rtype, pad):
    if pad:
        q = dns.message.make_query(name, rtype, use_edns=0, pad=128, want_dnssec=False)
    else:
        q = dns.message.make_query(name, rtype, use_edns=0, want_dnssec=False)
    q.id = 0  # RFC 8484 recommends ID 0 for cache-friendliness
    return q


def padding_len(msg):
    for opt in msg.options:
        if opt.otype == dns.edns.OptionType.PADDING:
            return len(opt.to_wire()) if hasattr(opt, "to_wire") else len(opt.data)
    return None


def do_doh(client, url, wire):
    r = client.post(url, content=wire, headers={
        "content-type": "application/dns-message", "accept": "application/dns-message"})
    r.raise_for_status()
    return r.content


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return buf


def do_dot(host, sni, wire):
    ctx = ssl.create_default_context(cafile=certifi.where())
    with socket.create_connection((host, 853), timeout=8) as raw:
        with ctx.wrap_socket(raw, server_hostname=sni) as s:
            s.sendall(struct.pack("!H", len(wire)) + wire)
            ln = struct.unpack("!H", recv_exact(s, 2))[0]
            return recv_exact(s, ln)


def main():
    rows = []
    client = httpx.Client(timeout=8.0, http2=True, verify=certifi.where())
    for name, url, dot_host, sni in RESOLVERS:
        for proto in ("DoH", "DoT"):
            for pad in (False, True):
                for qname, rtype in QUERIES:
                    q = build_query(qname, rtype, pad)
                    wire = q.to_wire()
                    row = dict(resolver=name, proto=proto, client_pad=int(pad), qname=qname,
                               rtype=rtype, query_len=len(wire), resp_len="", resp_pad_len="",
                               resp_has_pad="", mod128="", mod468="", error="")
                    try:
                        t0 = time.time()
                        resp = do_doh(client, url, wire) if proto == "DoH" else do_dot(dot_host, sni, wire)
                        m = dns.message.from_wire(resp)
                        pl = padding_len(m)
                        row.update(resp_len=len(resp), resp_pad_len=pl if pl is not None else "",
                                   resp_has_pad=int(pl is not None), mod128=len(resp) % 128,
                                   mod468=len(resp) % 468, rtt_ms=round(1000 * (time.time() - t0), 1))
                    except Exception as e:  # record, never crash the audit
                        row["error"] = type(e).__name__ + ": " + str(e)[:80]
                    rows.append(row)
                    time.sleep(0.15)
            print(name, proto, "done", flush=True)

    keys = ["resolver", "proto", "client_pad", "qname", "rtype", "query_len", "resp_len",
            "resp_pad_len", "resp_has_pad", "mod128", "mod468", "rtt_ms", "error"]
    with open(os.path.join(OUT, "padding_audit_raw.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})

    # Summary per resolver x proto x client_pad
    agg = defaultdict(list)
    for r in rows:
        agg[(r["resolver"], r["proto"], r["client_pad"])].append(r)
    summ = []
    for (res, proto, cp), rs in agg.items():
        ok = [r for r in rs if not r["error"]]
        n = len(ok)
        if n == 0:
            summ.append(dict(resolver=res, proto=proto, client_pad=cp, n_ok=0, n_err=len(rs),
                             pad_rate="", on128="", on468="", distinct_lengths="", lengths="",
                             verdict="unreachable"))
            continue
        lens = sorted({r["resp_len"] for r in ok})
        pad_rate = sum(r["resp_has_pad"] for r in ok) / n
        on128 = sum(r["mod128"] == 0 for r in ok) / n
        on468 = sum(r["mod468"] == 0 for r in ok) / n
        if pad_rate == 0:
            verdict = "no padding"
        elif on468 >= 0.9:
            verdict = "pads to 468 (RFC 8467)"
        elif on128 >= 0.9:
            verdict = "pads to 128"
        else:
            verdict = "pads, non-standard block"
        summ.append(dict(resolver=res, proto=proto, client_pad=cp, n_ok=n, n_err=len(rs) - n,
                         pad_rate=round(pad_rate, 2), on128=round(on128, 2), on468=round(on468, 2),
                         distinct_lengths=len(lens), lengths=" ".join(map(str, lens)), verdict=verdict))
    keys = ["resolver", "proto", "client_pad", "n_ok", "n_err", "pad_rate", "on128", "on468",
            "distinct_lengths", "lengths", "verdict"]
    with open(os.path.join(OUT, "padding_audit_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(summ)
    for s in summ:
        print(f"{s['resolver']:14s} {s['proto']} pad={s['client_pad']} ok={s['n_ok']:2} "
              f"padrate={s['pad_rate']} on128={s['on128']} on468={s['on468']} "
              f"nlen={s['distinct_lengths']} -> {s['verdict']}")


if __name__ == "__main__":
    main()
