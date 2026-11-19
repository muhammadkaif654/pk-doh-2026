"""Track B - scripted, unattended collection of DoH traces (PK-DoH-2026).

Per visit (mirrors Siby et al.'s browse_chrome.sh, adapted to Chrome's native DoH):
  1. fresh Chrome profile (empty HTTP and DNS cache) whose Local State forces
     Secure DNS = "secure" with a single DoH template pointing at a resolver IP;
  2. start dumpcap filtered to that resolver IP, TCP/UDP 443;
  3. load http://<site> headless (30 s page-load timeout) and wait 5 s idle;
  4. quit Chrome, wait 2 s, stop dumpcap; store pcapng + metadata row.

QUIC is disabled (--disable-quic) so the DoH channel is HTTP/2 over TLS/TCP, the
transport of the 2020 attack. Sites are visited round-robin, in a freshly
shuffled order every round, so each site's samples spread across the run.

Two workers may run in parallel on the SAME resolver by using its two anycast
addresses (1.1.1.1 / 1.0.0.1, 9.9.9.9 / 149.112.112.112): the capture filter is
per address, so traces never mix.

Only traffic we generate is captured. No third-party traffic is recorded.
"""
import argparse, csv, json, os, random, shutil, subprocess, sys, tempfile, time, traceback
from datetime import datetime, timezone

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException

DUMPCAP = r"C:\Program Files\Wireshark\dumpcap.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CHROMEDRIVER = os.path.join(ROOT, "tools", "chromedriver-win64", "chromedriver.exe")

RESOLVER_IPS = {
    # four addresses of the same service each, verified to answer identically (same padding)
    "cloudflare": ["1.1.1.1", "1.0.0.1", "162.159.36.1", "162.159.46.1"],
    "quad9": ["9.9.9.9", "149.112.112.112", "9.9.9.10", "149.112.112.10"],
    "google": ["8.8.8.8", "8.8.4.4"],
}


def read_sites(path):
    sites = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sites.append(row)
    return sites


def make_profile(ip):
    d = tempfile.mkdtemp(prefix="dohwf_")
    local_state = {"dns_over_https": {"mode": "secure", "templates": f"https://{ip}/dns-query"},
                   "browser": {"has_seen_welcome_page": True}}
    with open(os.path.join(d, "Local State"), "w") as f:
        json.dump(local_state, f)
    return d


def start_capture(iface, ip, out):
    flt = f"host {ip} and (tcp port 443 or udp port 443)"
    p = subprocess.Popen([DUMPCAP, "-i", iface, "-f", flt, "-w", out, "-q"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return p


def stop_capture(p):
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()


def visit(url, profile, timeout=30, idle=5):
    opts = webdriver.ChromeOptions()
    for a in ["--headless=new", f"--user-data-dir={profile}", "--disable-quic",
              "--no-first-run", "--no-default-browser-check", "--disable-sync",
              "--disable-background-networking", "--disable-component-update",
              "--disable-default-apps", "--disable-extensions", "--mute-audio",
              "--window-size=1366,768", "--disable-features=Translate,OptimizationHints,MediaRouter"]:
        opts.add_argument(a)
    status, title = "ok", ""
    t0 = time.time()
    driver = webdriver.Chrome(options=opts, service=Service(CHROMEDRIVER))
    try:
        driver.set_page_load_timeout(timeout)
        try:
            driver.get(url)
        except TimeoutException:
            status = "timeout"
        time.sleep(idle)
        try:
            title = (driver.title or "")[:80]
        except WebDriverException:
            pass
    except WebDriverException as e:
        status = "error:" + str(e).splitlines()[0][:80]
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    return status, title, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolver", required=True, choices=RESOLVER_IPS)
    ap.add_argument("--ip-index", type=int, default=0, help="which anycast address (0/1)")
    ap.add_argument("--network", required=True, help="label, e.g. wifi_home, mobile_4g")
    ap.add_argument("--iface", required=True, help="dumpcap interface name or number")
    ap.add_argument("--sites", default=os.path.join(HERE, "sites.csv"))
    ap.add_argument("--rounds", type=int, default=20)
    ap.add_argument("--start-round", type=int, default=0)
    ap.add_argument("--only", default="", help="comma list of site ids (testing)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--stride", type=int, default=0, help="number of workers sharing this resolver (default: number of addresses)")
    args = ap.parse_args()

    ip = RESOLVER_IPS[args.resolver][args.ip_index]
    cond = f"{args.network}_{args.resolver}"
    out_dir = os.path.join(ROOT, "data", "pcap", cond)
    os.makedirs(out_dir, exist_ok=True)
    meta_path = os.path.join(ROOT, "data", "pcap", f"{cond}_ip{args.ip_index}_meta.csv")
    new_meta = not os.path.exists(meta_path)
    meta = open(meta_path, "a", newline="", encoding="utf-8")
    mw = csv.writer(meta)
    if new_meta:
        mw.writerow(["file", "site_id", "domain", "group", "round", "resolver", "resolver_ip",
                     "network", "utc_start", "status", "title", "seconds", "pcap_bytes"])

    sites = read_sites(args.sites)
    if args.only:
        keep = set(args.only.split(","))
        sites = [s for s in sites if s["site_id"] in keep]
    rng = random.Random(args.seed * 1000 + args.ip_index)
    # each worker of a resolver takes alternate rounds so the two never repeat work
    for rnd in range(args.start_round, args.rounds):
        stride = args.stride or len(RESOLVER_IPS[args.resolver])
        if args.ip_index % stride != rnd % stride and not args.only:
            continue
        order = sites[:]
        rng.shuffle(order)
        for s in order:
            fname = f"{s['site_id']}_r{rnd:02d}.pcapng"
            fpath = os.path.join(out_dir, fname)
            if os.path.exists(fpath) and os.path.getsize(fpath) > 0 and not args.only:
                continue
            profile = make_profile(ip)
            utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
            cap = start_capture(args.iface, ip, fpath)
            time.sleep(1.5)
            try:
                status, title, secs = visit("http://" + s["domain"], profile)
            except Exception as e:
                status, title, secs = "crash:" + type(e).__name__, "", 0
                traceback.print_exc()
            time.sleep(2)
            stop_capture(cap)
            shutil.rmtree(profile, ignore_errors=True)
            size = os.path.getsize(fpath) if os.path.exists(fpath) else 0
            mw.writerow([fname, s["site_id"], s["domain"], s["group"], rnd, args.resolver, ip,
                         args.network, utc, status, title, round(secs, 1), size])
            meta.flush()
            print(f"[{cond} ip{args.ip_index}] r{rnd} {s['site_id']} {s['domain']:28s} "
                  f"{status:8s} {secs:5.1f}s {size}B", flush=True)
    meta.close()


if __name__ == "__main__":
    main()
