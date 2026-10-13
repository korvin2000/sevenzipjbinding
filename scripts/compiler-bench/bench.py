"""Benchmark driver for .github/workflows/windows-x64-compilers.yml (runs on the Windows runner).

Every build (one dir per <compiler>-<variant> with 7zz.exe, sevenzipjbinding.jar,
sevenzipjbinding-Windows-amd64.jar, info.txt) is run on the SAME machine, in interleaved rounds whose
order rotates, so runner drift / noisy neighbours hit all builds alike. Reported numbers are medians.

  7zz b -mmt1          LZMA single-thread rating (MIPS) - 7-Zip's canonical CPU benchmark
  7zz b                LZMA all-threads rating (MIPS)
  7zz b -mmt1 -mm=*    per-method speed (KiB/s): LZMA, Deflate, BZip2, PPMd, AES, CRC, SHA, BCJ, ...
  JniBench             compress + extract an in-memory corpus through the JNI binding (MiB/s)
"""
import argparse
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time

HIGH = getattr(subprocess, "HIGH_PRIORITY_CLASS", 0)


def run(cmd, affinity=0, timeout=3600):
    """High priority; affinity = CPU mask (single-thread runs are pinned to one core, not core 0)."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         encoding="utf-8", errors="replace", creationflags=HIGH)
    if affinity and os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetProcessAffinityMask(int(p._handle), affinity)
    out, _ = p.communicate(timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"{cmd} failed ({p.returncode}):\n{out[-3000:]}")
    return out


PIN1 = 0b10  # CPU 1


def parse_lzma(out):
    """Avr: compress | decompress rating, Tot: overall rating (last column = Rating MIPS)."""
    r = {}
    for line in out.splitlines():
        if line.startswith("Avr:") and "|" in line:
            left, right = line[4:].split("|", 1)
            r["compress"], r["decompress"] = int(left.split()[-1]), int(right.split()[-1])
        elif line.startswith("Tot:"):
            r["total"] = int(line.split()[-1])
    if len(r) != 3:
        raise ValueError("cannot parse 7zz b output:\n" + out[-2000:])
    return r


ROW = re.compile(r"^(\S+)\s+(\d+)\s+\d+\s+\d+\s+\d+")
CONT = re.compile(r"^\s+(\d+)\s+\d+\s+\d+\s+\d+")


def parse_methods(out):
    """Rows after the 'Method' header: '<name> speed usage r/u rating ...' (encode / hash), optionally
    followed by an indented decode row. Speed is KiB/s."""
    res, cur, started = {}, None, False
    for line in out.splitlines():
        if line.startswith("Method"):
            started = True
            continue
        if not started or line.startswith(("CPU", "Tot:", "Avr:", "---")):
            cur = None
            continue
        m = ROW.match(line)
        if m:
            cur = m.group(1)
            res[cur] = int(m.group(2))
            continue
        m = CONT.match(line)
        if m and cur:
            res[cur + " (dec)"] = int(m.group(1))
            cur = None
    if not res:
        raise ValueError("cannot parse 7zz b -mm=* output:\n" + out[-2000:])
    return res


def median(xs):
    return statistics.median(xs) if xs else float("nan")


def geomean(xs):
    xs = [x for x in xs if x > 0]
    return math.exp(sum(map(math.log, xs)) / len(xs)) if xs else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--builds-dir", required=True)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--methods-rounds", type=int, default=2, help="rounds of the slow '7zz b 1 -mm=*' sweep")
    ap.add_argument("--dict", default="22", help="LZMA bench max dictionary (log2): dicts 18..N are run")
    ap.add_argument("--jni-rounds", type=int, default=2)
    ap.add_argument("--jni-reps", type=int, default=2)
    ap.add_argument("--jni-classes", help="dir with compiled JniBench.class (skip JNI bench if absent)")
    ap.add_argument("--corpus", nargs="*", default=[])
    ap.add_argument("--corpus-mib", type=int, default=32)
    ap.add_argument("--baseline", default="gcc17-base")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    builds = sorted(d for d in os.listdir(a.builds_dir)
                    if os.path.isfile(os.path.join(a.builds_dir, d, "7zz.exe")))
    if not builds:
        sys.exit("no builds found")
    exe = {b: os.path.join(a.builds_dir, b, "7zz.exe") for b in builds}
    info = {}
    for b in builds:
        p = os.path.join(a.builds_dir, b, "info.txt")
        info[b] = open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""
    base = a.baseline if a.baseline in builds else builds[0]

    raw = {"lzma1": {b: [] for b in builds}, "lzmaN": {b: [] for b in builds},
           "methods": {b: [] for b in builds}, "jni": {b: [] for b in builds}}
    header = run([exe[builds[0]], "b", "-mmt1", "-md18"]).split("Compressing")[0]  # warm-up + CPU/system info
    header = "\n".join(l for l in header.splitlines() if l.strip())
    print(header, flush=True)

    t_start = time.time()

    def rotation(r):
        order = builds[r % len(builds):] + builds[:r % len(builds)]
        return order[::-1] if r % 2 else order

    for r in range(a.rounds):
        for b in rotation(r):
            raw["lzma1"][b].append(parse_lzma(run([exe[b], "b", "-mmt1", f"-md{a.dict}"], PIN1)))
            raw["lzmaN"][b].append(parse_lzma(run([exe[b], "b", f"-md{a.dict}"])))
            print(f"[{time.time() - t_start:6.0f}s] LZMA round {r + 1}/{a.rounds} {b}: "
                  f"1T {raw['lzma1'][b][-1]['total']} MIPS, NT {raw['lzmaN'][b][-1]['total']} MIPS", flush=True)
    # not pinned: the sweep includes explicit 2-thread rows (LZMA:x5:mt2, BZip2:x5:mt2)
    for r in range(a.methods_rounds):
        for b in rotation(r):
            out = run([exe[b], "b", "1", "-mmt1", "-mm=*"])
            raw["methods"][b].append(parse_methods(out))
            if r == 0:
                with open(os.path.join(a.out, f"7zz-methods-{b}.txt"), "w", encoding="utf-8") as f:
                    f.write(out)
            print(f"[{time.time() - t_start:6.0f}s] methods round {r + 1}/{a.methods_rounds} {b}", flush=True)

    if a.jni_classes and a.corpus:
        for r in range(a.jni_rounds):
            for b in rotation(r):
                d = os.path.join(a.builds_dir, b)
                cp = os.pathsep.join([os.path.join(d, "sevenzipjbinding.jar"),
                                      os.path.join(d, "sevenzipjbinding-Windows-amd64.jar"), a.jni_classes])
                out = run(["java", "-Xmx3g", "-cp", cp, "JniBench", b, str(a.jni_reps), str(a.corpus_mib)]
                          + a.corpus)
                rows = [l.split(",") for l in out.splitlines() if l.startswith(b + ",")]
                raw["jni"][b].append({f"{x[1]} {x[2]}": float(x[3]) for x in rows})  # min ms
                print(f"[{time.time() - t_start:6.0f}s] JNI round {r + 1}/{a.jni_rounds} {b}", flush=True)

    with open(os.path.join(a.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump({"header": header, "info": info, "raw": raw}, f, indent=1)

    # ---------------------------------------------------------------- summary (markdown)
    md = ["## 7-Zip Windows x64 compiler benchmark", "", "```", header, "```", "",
          f"Rounds: LZMA {a.rounds}, `-mm=*` {a.methods_rounds}, JNI {a.jni_rounds} (interleaved, rotating order); "
          f"numbers are medians (JNI: best). "
          f"Ratios are relative to `{base}`.", "", "### Builds", "", "| build | compiler | flags |", "|---|---|---|"]
    for b in builds:
        kv = dict(l.split(":", 1) for l in info[b].splitlines() if ":" in l)
        md.append(f"| {b} | {kv.get('compiler', '').strip()} | `{kv.get('flags', '').strip()}` |")

    def lz(kind, b, key):
        return median([x[key] for x in raw[kind][b]])

    md += ["", f"### LZMA rating (7zz b -md{a.dict}), MIPS - higher is better (1T pinned to one core)", "",
           "| build | 1T compress | 1T decompress | 1T total | vs base | NT compress | NT decompress | NT total | vs base |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for b in builds:
        t1, tn = lz("lzma1", b, "total"), lz("lzmaN", b, "total")
        md.append(f"| {b} | {lz('lzma1', b, 'compress'):.0f} | {lz('lzma1', b, 'decompress'):.0f} | {t1:.0f} | "
                  f"{t1 / lz('lzma1', base, 'total'):.3f} | {lz('lzmaN', b, 'compress'):.0f} | "
                  f"{lz('lzmaN', b, 'decompress'):.0f} | {tn:.0f} | {tn / lz('lzmaN', base, 'total'):.3f} |")

    methods = [m for m in raw["methods"][base][0]]
    med = {b: {m: median([x.get(m, 0) for x in raw["methods"][b]]) for m in methods} for b in builds}
    score = {b: geomean([med[b][m] / med[base][m] for m in methods if med[base][m] > 0]) for b in builds}
    md += ["", "### Overall (geometric mean of all `-mm=*` method speeds, single thread) vs base", "",
           "| rank | build | score |", "|---:|---|---:|"]
    for i, b in enumerate(sorted(builds, key=lambda x: -score[x]), 1):
        md.append(f"| {i} | {b} | {score[b]:.3f} |")

    md += ["", "### Per-method speed, single thread (MB/s; `(dec)` = decode) - higher is better", "",
           "| method | " + " | ".join(builds) + " |", "|---|" + "---:|" * len(builds)]
    for m in methods:
        best = max(med[b][m] for b in builds)
        cells = [(f"**{med[b][m] / 1000:.1f}**" if med[b][m] == best else f"{med[b][m] / 1000:.1f}") for b in builds]
        md.append(f"| {m} | " + " | ".join(cells) + " |")

    if any(raw["jni"][b] for b in builds):
        keys = list(raw["jni"][builds[0]][0])
        md += ["", f"### JNI binding (JniBench, {a.corpus_mib} MiB corpus cap), best time ms - lower is better", "",
               "| case | " + " | ".join(builds) + " |", "|---|" + "---:|" * len(builds)]
        for k in keys:
            vals = {b: min(x[k] for x in raw["jni"][b]) for b in builds}
            best = min(vals.values())
            md.append(f"| {k} | " + " | ".join((f"**{vals[b]:.0f}**" if vals[b] == best else f"{vals[b]:.0f}")
                                               for b in builds) + " |")
        jscore = {b: geomean([min(x[k] for x in raw["jni"][base]) / min(x[k] for x in raw["jni"][b])
                              for k in keys]) for b in builds}
        md += ["", "JNI score (geomean speed vs base): " +
               ", ".join(f"{b} {jscore[b]:.3f}" for b in sorted(builds, key=lambda x: -jscore[x]))]

    text = "\n".join(md) + "\n"
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as f:
        f.write(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text)
    print(text)


if __name__ == "__main__":
    main()
