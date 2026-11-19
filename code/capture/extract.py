"""Preprocessing (Step 3): pcapng -> sequence of signed TLS record sizes + timestamps.

For each capture we keep the TLS records of the DoH flow (resolver IP, TCP 443)
and output, per trace:
    lengths : signed TLS record lengths (+ client->resolver, - resolver->client),
              the representation of Siby et al. (NDSS 2020);
    times   : record timestamps relative to the first kept record (seconds).

TLS 1.3 encrypts the handshake inside application-data records (type 23). The
2018-19 data was TLS 1.2, where those were handshake records (type 22) and were
excluded. To keep the representation comparable we drop, per TCP connection,
every type-23 record that precedes the client's Finished (the client's first
type-23 record) and that Finished itself. Session tickets (sent after the
handshake) are handshake records in TLS 1.2, so we also drop server type-23
records of length <= 300 that arrive before the client's first post-handshake
record. The resulting trace begins with the first real DoH exchange.

Output: one JSON-lines file per condition in data/traces/<cond>.jsonl
"""
import csv, glob, json, os, subprocess, sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RESOLVER_IPS = {"1.1.1.1", "1.0.0.1", "162.159.36.1", "162.159.46.1", "9.9.9.9", "149.112.112.112",
                "9.9.9.10", "149.112.112.10", "8.8.8.8", "8.8.4.4"}


def parse_pcap(path):
    cmd = [TSHARK, "-r", path, "-o", "tcp.desegment_tcp_streams:TRUE", "-Y", "tls.record",
           "-T", "fields", "-E", "separator=\t", "-E", "occurrence=a", "-E", "aggregator=,",
           "-e", "frame.time_epoch", "-e", "ip.src", "-e", "tcp.stream",
           "-e", "tls.record.content_type", "-e", "tls.record.opaque_type", "-e", "tls.record.length"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    per_stream = defaultdict(list)  # stream -> list of (t, dir, ctype, len)
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 6 or not parts[5]:
            continue
        t = float(parts[0]); src = parts[1]; st = parts[2]
        d = -1 if src in RESOLVER_IPS else 1
        # TLS 1.3: plaintext-typed records (handshake 22, CCS 20) carry content_type and
        # always precede the encrypted ones (opaque_type 23) inside a packet.
        typed = [int(x) for x in parts[3].split(",") if x]
        opaque = [int(x) for x in parts[4].split(",") if x]
        ctypes = typed + opaque
        lens = parts[5].split(",")
        if len(ctypes) != len(lens):
            continue
        for c, l in zip(ctypes, lens):
            per_stream[st].append((t, d, int(c), int(l)))
    recs = []
    for st, rs in per_stream.items():
        seen_client_fin = False
        seen_request = False
        for (t, d, c, l) in rs:
            if c != 23:
                continue  # handshake (22), CCS (20), alert (21)
            if not seen_client_fin:
                if d == 1:
                    seen_client_fin = True  # client Finished: drop it
                continue  # encrypted server handshake records: drop
            if not seen_request:
                if d == 1:
                    seen_request = True
                elif l <= 300:
                    continue  # NewSessionTicket(s) before first request
            recs.append((t, d * l))
    recs.sort(key=lambda r: r[0])
    if not recs:
        return [], []
    t0 = recs[0][0]
    return [r[1] for r in recs], [round(r[0] - t0, 6) for r in recs]


def work(item):
    path, meta = item
    lengths, times = parse_pcap(path)
    meta = dict(meta)
    meta["lengths"] = lengths
    meta["times"] = times
    return meta


def main(cond_glob="*"):
    pcap_root = os.path.join(ROOT, "data", "pcap")
    out_root = os.path.join(ROOT, "data", "traces")
    os.makedirs(out_root, exist_ok=True)
    for cond_dir in sorted(glob.glob(os.path.join(pcap_root, cond_glob))):
        if not os.path.isdir(cond_dir):
            continue
        cond = os.path.basename(cond_dir)
        metas = {}
        for mp in glob.glob(os.path.join(pcap_root, f"{cond}_ip*_meta.csv")):
            with open(mp, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    metas[r["file"]] = r  # last write wins (re-runs)
        items = [(os.path.join(cond_dir, fn), m) for fn, m in metas.items()
                 if os.path.exists(os.path.join(cond_dir, fn))]
        with ProcessPoolExecutor(max_workers=8) as ex:
            rows = list(ex.map(work, items, chunksize=8))
        out = os.path.join(out_root, f"{cond}.jsonl")
        with open(out, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        print(cond, len(rows), "traces ->", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "*")
