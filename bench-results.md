# Benchmark results: GCC 16.2 / 17 snapshot vs Clang 23.1 / 24 nightly, Windows x64 (2026-10-13)

7-Zip-JBinding 26.03-2.3 (7-Zip 26.03 engine), Windows x64 native library and 7-Zip's own `7zz.exe`
built from the same `7zip/` sources by
[`windows-x64-compilers.yml`](.github/workflows/windows-x64-compilers.yml). CI runs:
[38397134132](https://github.com/korvin2000/sevenzipjbinding/actions/runs/38397134132) (development
compilers) and [38413713336](https://github.com/korvin2000/sevenzipjbinding/actions/runs/38413713336)
(stable releases: GCC 16.2.0 and Clang 23.1.3, plus the two nightly `avx2-lto` builds for reference).

## TL;DR

* **Latest stable releases (GCC 16.2.0, Clang 23.1.3) and development builds (GCC 17.0.0 snapshot,
  Clang 24.0.0git nightly) all build the project with GitHub CI and pass the full test suite in every
  variant.**
* **The nightlies bring no speed gain.** On the same machine, Clang 23.1.3 ≈ Clang 24 nightly (codec
  geomean ratio 0.999; Java binding +1.4% for 23.1.3), and GCC 16.2.0 ≈ GCC 17 snapshot (1.004).
* **Release AVX2 build: `clang23-avx2-lto`** (stable Clang 23.1.3, `-O3 -march=x86-64-v3 -ffast-math
  -flto`). It is the fastest build of the stable-compiler run: best Java-binding score (1.024 vs
  GCC 16.2 `-O2`; GCC 16.2 `avx2-lto` scores 1.013) and best single-thread LZMA rating (+4.1%). It
  also uses a released, reproducible compiler.
* **Both development compilers build the project and pass the full JUnit suite (18/18 ctest bundles)
  on a native Windows x64 JVM, in every variant**, including `-O3 -march=x86-64-v3 -ffast-math -flto`.
* **There is no big winner: GCC 17 and Clang 24 end up within about 1-3% of each other overall**, and
  the optimized AVX2 builds land within about ±3% of the plain `-O2` generic build (sometimes slower). 7-Zip's hot
  loops are already hand-tuned and CPU-dispatched (AES-NI, SHA-NI, CRC, AVX2 match finder), so `-O3`,
  AVX2 and fast-math have little left to optimize.
* Development-compiler run: **`clang-nightly-avx2-lto`** (Clang 24.0.0git, `-O3 -march=x86-64-v3
  -ffast-math -flto`) was the best (it shipped in release `-ci2`; `-ci3` ships the equivalent Clang
  23.1.3 build):
  * best end-to-end JNI score on both machines (+0.1% / +2.7% vs the GCC 17 `-O2` baseline; +1.1% /
    +2.8% vs `gcc17-avx2-lto`);
  * fastest BZip2 compression (5-10%) and ZIP/Deflate (1-4%);
  * within ±3% on LZMA/7z extraction;
  * GCC 17 (its plain `-O2` build) is 2-5% faster at 7z/LZMA2 single-thread compression.
* Codec-level differences are much larger than the overall ones and consistent on both CPUs:

| Faster with **Clang 24** | Faster with **GCC 17** |
|---|---|
| RISC-V filter +39-41%, BLAKE2sp 2/3-way +4-47%, CRC32 +6-10%, CRC64 +1-6%, LZMA fast mode (x1) compression +5-15%, Deflate/Deflate64 +1-8%, BZip2 L9 compression through the binding +5-10%, software AES decode in the generic build +12-16% | SHA1 software +32-39% (AVX2 builds), MD5 +12-22%, SHA-256/512 software 0-10%, BZip2 decode +10-27% without LTO (LTO evens it out), PPMd +2-11% (AVX2 builds), LZMA decode 0-6%, Delta filter +35% (Zen 4 only) |

* `-march=x86-64-v3` **hurts** some codecs: XXH64 is 25-39% slower with both compilers; with Clang,
  software AES is 28% slower and SHA1 software 14% slower. It helps SHA3-256 (+18-29%) and BLAKE2sp.

## Setup

| | |
|---|---|
| GCC | **17.0.0 20261011 (experimental)**, snapshot `gcc-17-20261011`, Linux-hosted x86_64-w64-mingw32 cross toolchain built in CI (binutils 2.47, mingw-w64 master `63ebe6c`, UCRT, win32 threads) |
| Clang | **24.0.0git** (llvm-project `dff64a2bf54d`), llvm-mingw `nightly` (UCRT, libc++, lld) |
| Variants | `base` = project defaults (`-O2`, generic x86-64); `avx2` = `-O3 -march=x86-64-v3 -ffast-math`; `avx2-lto` = `avx2` + `-flto=auto` (GCC) / `-flto` (Clang) |
| Machine A (CI) | `windows-latest` GitHub runner (Windows Server 2025, Hyper-V): **AMD EPYC 9V74** (Zen 4), 4 vCPU, 16 GB |
| Machine B (local) | Windows 10 laptop: **AMD Ryzen 5 5500U** (Zen 2), 6C/12T, 32 GB |
| Benchmarks | `7zz b -mmt1 -md22` (pinned to one core) and `7zz b -md22` (all threads): CI 7 rounds, local 5 rounds. `7zz b 1 -mmt1 -mm=*` (every method): CI 2 rounds, local 1 round. JniBench (compress + extract a 32 MiB corpus of 7-Zip sources + Windows DLLs in memory through the binding; best of 4): both machines. All builds interleaved in rotating order on the same machine; medians. |

## Measurement quality (read this before the numbers)

* **Stable:** single-thread LZMA decompression (coefficient of variation ≈1% on CI), the per-method
  speeds, and JniBench best-of times.
* **Noisy on the CI VM:** single-thread LZMA *compression* (cv ≈15%, bimodal ~4.5k/~6.7k MIPS), and
  multi-thread LZMA *decompression*, which is **bimodal for every build** (~8.5k or ~15.5k MIPS, cv
  22-29%; noisy neighbours / vCPU scheduling on the shared host). The CI multi-thread table below is
  therefore not usable for comparing compilers; on the local machine the same metric is tight (cv < 3%
  in most rounds) and all builds land within ±3%.
* As a rule of thumb (and per the Codex review of the method), differences under about 2-3% are within
  run-to-run noise unless they repeat on both machines.

## LZMA rating (7zz b), MIPS: single thread

| build | CI compress | CI decompress | local compress | local decompress |
|---|---:|---:|---:|---:|
| gcc17-base | 5265 | **4848** | 4063 | **4413** |
| gcc17-avx2 | **6128** | 4784 | 4479 | 4353 |
| gcc17-avx2-lto | 4979 | 4749 | 4639 | 4405 |
| clang-nightly-base | 5507 | 4679 | 4480 | 4254 |
| clang-nightly-avx2 | 4700 | 4731 | 4587 | 4349 |
| clang-nightly-avx2-lto | 5549 | 4741 | **4714** | 4376 |

Decompression (the stable metric): all six builds are within 3.6% of each other on both machines, and
GCC is 0-4% ahead. Compression is within noise.

## Overall: geometric mean of all `-mm=*` method speeds (single thread), vs `gcc17-base`

| build | CI (Zen 4) | local (Zen 2) |
|---|---:|---:|
| gcc17-base | 1.000 | 1.000 |
| gcc17-avx2 | 0.994 | 1.008 |
| gcc17-avx2-lto | **1.005** | 1.011 |
| clang-nightly-base | **1.005** | **1.028** |
| clang-nightly-avx2 | 0.979 | 0.972 |
| clang-nightly-avx2-lto | 0.994 | 1.020 |

Clang/GCC ratio of these geomeans, by variant: base 1.005 / 1.028; avx2 0.985 / 0.964; avx2-lto
0.989 / 1.009 (CI / local).

## JNI binding end-to-end (JniBench), best time in ms (lower is better)

| case | machine | gcc17-base | gcc17-avx2 | gcc17-avx2-lto | clang-base | clang-avx2 | clang-avx2-lto |
|---|---|---:|---:|---:|---:|---:|---:|
| 7z LZMA2 L5, 1 thread, compress | CI | **8600** | 8860 | 8800 | 8981 | 9145 | 9014 |
| | local | **11154** | 11210 | 11239 | 11386 | 11346 | 11353 |
| 7z LZMA2 L5, 1 thread, extract | CI | **294** | 302 | 302 | 302 | 307 | 302 |
| | local | 341 | 344 | 339 | 340 | 340 | **336** |
| 7z LZMA2 L5, all threads, compress | CI | 4823 | 4905 | 4840 | 4995 | 4940 | **4812** |
| | local | 6119 | 6285 | 6272 | 6328 | 6364 | **6114** |
| ZIP Deflate L5 compress | CI | 942 | 949 | 952 | 951 | 945 | **927** |
| | local | 545 | 544 | 544 | 533 | 541 | **522** |
| ZIP Deflate extract | CI | 138 | 140 | 138 | 135 | 136 | **133** |
| | local | 154 | 152 | 151 | 150 | **147** | 148 |
| BZip2 L9 compress | CI | 7993 | 7973 | 8049 | 7658 | 7340 | **7293** |
| | local | 3436 | 3502 | 3384 | **3162** | 3220 | 3205 |
| BZip2 extract | CI | **326** | **326** | **326** | 351 | 346 | 342 |
| | local | 427 | 427 | 428 | 457 | 443 | **411** |
| **JNI score** (geomean speed vs gcc17-base) | CI | 1.000 | 0.987 | 0.990 | 0.983 | 0.987 | **1.001** |
| | local | 1.000 | 0.994 | 0.999 | 1.003 | 1.003 | **1.027** |

(7z extraction of all-thread archives ≈ the single-thread numbers and is omitted.)

## Clang/GCC speed ratio per method (>1 = Clang faster), same variant, CI | local

| method | base CI | base local | avx2 CI | avx2 local | avx2-lto CI | avx2-lto local |
|---|---:|---:|---:|---:|---:|---:|
| LZMA:x1 | 1.06 | 1.15 | 1.07 | 0.97 | 1.05 | 1.08 |
| LZMA:x1 (dec) | 0.95 | 0.96 | 0.99 | 0.97 | 1.00 | 0.99 |
| LZMA:x3 | 1.10 | 1.03 | 1.17 | 1.05 | 0.82 | 1.04 |
| LZMA:x3 (dec) | 0.96 | 0.99 | 0.99 | 0.99 | 0.99 | 0.99 |
| LZMA:x5:mt1 | 0.99 | 0.98 | 1.06 | 0.98 | 0.97 | 0.96 |
| LZMA:x5:mt1 (dec) | 0.96 | 0.95 | 0.99 | 0.99 | 0.99 | 0.98 |
| LZMA:x5:mt2 | 1.00 | 0.96 | 0.96 | 1.07 | 1.01 | 0.97 |
| LZMA:x5:mt2 (dec) | 0.96 | 0.94 | 0.99 | 0.99 | 0.99 | 0.99 |
| Deflate:x1 | 1.02 | 1.01 | 1.02 | 1.03 | 1.06 | 1.03 |
| Deflate:x1 (dec) | 1.01 | 1.04 | 0.99 | 1.04 | 1.02 | 1.03 |
| Deflate:x5 | 0.99 | 1.07 | 1.03 | 0.96 | 1.03 | 1.08 |
| Deflate:x5 (dec) | 1.02 | 1.01 | 0.99 | 1.05 | 1.01 | 1.02 |
| Deflate:x7 | 0.96 | 1.01 | 1.03 | 1.09 | 1.03 | 1.06 |
| Deflate:x7 (dec) | 1.02 | 1.04 | 0.99 | 1.04 | 1.02 | 1.02 |
| Deflate64:x5 | 1.00 | 1.04 | 1.03 | 0.41 | 1.02 | 1.04 |
| Deflate64:x5 (dec) | 1.01 | 1.03 | 0.99 | 0.74 | 1.01 | 1.00 |
| BZip2:x1 | 0.97 | 1.02 | 1.00 | 0.66 | 1.00 | 0.97 |
| BZip2:x1 (dec) | 0.87 | 0.85 | 0.89 | 0.85 | 0.97 | 0.98 |
| BZip2:x5 | 1.01 | 1.11 | 1.00 | 1.12 | 1.00 | 0.93 |
| BZip2:x5 (dec) | 0.90 | 0.90 | 0.91 | 0.83 | 0.97 | 0.95 |
| BZip2:x5:mt2 | 1.00 | 1.05 | 0.94 | 0.84 | 0.98 | 1.00 |
| BZip2:x5:mt2 (dec) | 0.84 | 0.83 | 0.81 | 0.83 | 0.97 | 1.01 |
| BZip2:x7 | 1.03 | 1.06 | 1.04 | 0.97 | 1.03 | 0.98 |
| BZip2:x7 (dec) | 0.90 | 0.85 | 0.91 | 0.79 | 0.99 | 1.05 |
| PPMD:x1 | 1.01 | 0.99 | 0.94 | 0.90 | 0.98 | 0.91 |
| PPMD:x1 (dec) | 1.07 | 0.99 | 0.97 | 0.92 | 0.98 | 0.95 |
| PPMD:x5 | 1.05 | 1.00 | 0.99 | 0.92 | 0.95 | 0.93 |
| PPMD:x5 (dec) | 1.13 | 1.01 | 0.99 | 0.94 | 0.94 | 0.98 |
| Swap4 | 0.99 | 0.99 | 0.97 | 1.02 | 0.99 | 0.98 |
| Swap4 (dec) | 0.99 | 1.02 | 0.98 | 0.94 | 0.99 | 1.03 |
| Delta:4 | 0.74 | 1.02 | 0.73 | 0.92 | 0.73 | 1.03 |
| Delta:4 (dec) | 0.93 | 1.11 | 0.90 | 1.04 | 0.90 | 1.06 |
| BCJ | 1.29 | 1.19 | 1.24 | 1.13 | 1.00 | 0.81 |
| BCJ (dec) | 0.87 | 1.20 | 0.93 | 1.19 | 0.97 | 0.99 |
| ARM64 | 0.97 | 1.25 | 0.89 | 1.24 | 0.89 | 1.19 |
| ARM64 (dec) | 0.99 | 0.92 | 0.90 | 1.26 | 0.89 | 1.28 |
| RISCV | 1.41 | 1.39 | 1.38 | 1.32 | 1.40 | 1.42 |
| RISCV (dec) | 1.40 | 1.36 | 1.79 | 1.29 | 1.87 | 1.63 |
| AES256CBC:1 | 0.99 | 1.10 | 0.72 | 0.79 | 0.74 | 0.79 |
| AES256CBC:1 (dec) | 1.12 | 1.16 | 0.79 | 0.83 | 0.81 | 0.84 |
| AES256CBC:2 | 1.00 | 1.00 | 1.00 | 0.98 | 1.00 | 1.00 |
| AES256CBC:2 (dec) | 1.00 | 1.00 | 0.98 | 1.00 | 1.00 | 1.01 |
| AES256CBC:3 | 1.00 | - | 1.00 | - | 1.00 | - |
| AES256CBC:3 (dec) | 1.00 | - | 0.99 | - | 1.00 | - |
| CRC32:12 | 1.08 | 1.10 | 1.06 | 1.08 | 1.10 | 1.09 |
| CRC64 | 1.06 | 1.06 | 1.01 | 1.01 | 1.05 | 1.03 |
| XXH64 | 1.00 | 1.00 | 0.91 | 0.93 | 0.91 | 0.93 |
| MD5 | 0.84 | 0.88 | 0.82 | 0.88 | 0.83 | 0.89 |
| SHA1:1 | 1.01 | 1.01 | 0.74 | 0.72 | 0.76 | 0.73 |
| SHA1:2 | 1.03 | 1.08 | 1.02 | 1.06 | 1.02 | 1.07 |
| SHA256:1 | 0.97 | 1.01 | 0.93 | 0.91 | 0.95 | 0.92 |
| SHA256:2 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.01 |
| SHA512:1 | 0.96 | 1.01 | 0.95 | 0.97 | 0.95 | 0.97 |
| SHA3-256 | 0.96 | 0.93 | 1.00 | 1.01 | 0.99 | 1.00 |
| BLAKE2sp:1 | 0.93 | 0.99 | 0.99 | 0.97 | 0.94 | 0.93 |
| BLAKE2sp:2 | 1.11 | 1.04 | 1.07 | 1.12 | 1.07 | 1.10 |
| BLAKE2sp:3 | 1.23 | 1.17 | 1.37 | 1.34 | 1.47 | 1.30 |

The local per-method numbers are a single round. Isolated outliers there (for example `avx2` Deflate64:x5
0.41 or BZip2:x1 0.66) are laptop noise, because the same rows are ≈1.0 on CI and in the LTO column.

## Stable compilers: GCC 16.2.0 vs Clang 23.1.3 (CI run 38413713336, AMD EPYC 7763 / Zen 3)

GCC 16.2.0: Linux-hosted cross toolchain built by the same recipe (mingw-w64 master, UCRT). Clang
23.1.3: llvm-mingw 20261006. The two development `avx2-lto` builds ran alongside on the same runner.
This runner was quiet: multi-thread cv ≤ 3%, single-thread decompression cv ≤ 2%.

| build | LZMA 1T compress | LZMA 1T decompress | LZMA NT total | codec geomean | Java binding score |
|---|---:|---:|---:|---:|---:|
| gcc16-base | 4783 | 4071 | 15113 | 1.000 | 1.000 |
| gcc16-avx2 | 4549 | 4082 | 15101 | 1.007 | 1.008 |
| gcc16-avx2-lto | 5036 | **4098** | 14899 | 1.003 | 1.013 |
| clang23-base | 4600 | 4032 | 14912 | **1.014** | 1.011 |
| clang23-avx2 | 4821 | 4035 | 14907 | 1.005 | 1.022 |
| **clang23-avx2-lto** | **5204** | 4012 | 14891 | 1.009 | **1.024** |
| gcc17-avx2-lto (snapshot) | 4916 | 4017 | 14705 | 0.999 | 0.995 |
| clang-nightly-avx2-lto | 4866 | 4013 | 14760 | 1.010 | 1.010 |

Head-to-head (codec geomean):
* Clang 23.1.3 / GCC 16.2: base 1.014, avx2 0.998, avx2-lto 1.006.
* Clang 23.1.3 / Clang 24 nightly (`avx2-lto`): 0.999.
* GCC 16.2 / GCC 17 snapshot (`avx2-lto`): 1.004.
* Same pattern as the development compilers: GCC is 1.5-4% faster at LZMA decompression, Clang is
  faster through the Java binding (BZip2 and LZMA2 compression), and `-O3`/AVX2 changes the totals
  by under 1%. Full tables: appendix C.

## Recommendation

* **Need maximum speed on AVX2 machines:** use the release's
  `sevenzipjbinding-26.03-2.3-Windows-amd64-avx2.zip`, a drop-in replacement for the `Windows-amd64`
  zip. From release `-ci3` on it is built with **stable Clang 23.1.3** (`clang23-avx2-lto`), the
  fastest build through the binding on the stable-compiler run and equal to Clang nightly
  elsewhere.
* **If 7z/LZMA2 compression throughput is all that matters:** GCC 17 (even at plain `-O2`) is 2-5%
  faster there. Build it with the same workflow (`only: gcc17-base` / `gcc17-avx2-lto`).
* **Portability first:** the generic `-O2` builds are within about 0-3% of the AVX2 builds overall.
  The portable `Windows-amd64` zip loses almost nothing and runs on every x86-64 CPU.
* `-ffast-math` has no measurable effect: the codecs use no floating point in their hot paths.
* LTO helps Clang (+1.6-5% geomean over plain `avx2`) more than GCC (+0.3-1.1%).

## Reproduce

* CI: push to the `compiler-bench` branch, or Actions → *Windows x64 compilers ...* → Run workflow
  (inputs: GCC snapshot, `stable` adds GCC 16.2 + Clang 23 as references, rounds). The results land in
  the run summary and in the `bench-results` artifact.
* Locally (Windows x64, Python 3, JDK 8+): download the `bin-*` artifacts into `dist/<build>/`, compile
  `scripts/compiler-bench/JniBench.java` against `sevenzipjbinding.jar`, then run
  `python scripts/compiler-bench/bench.py --builds-dir dist --jni-classes <dir> --corpus 7zip <dll-dir> --out results`.

---

## Appendix A: full CI results (AMD EPYC 9V74, Zen 4)


```
7-Zip (z) 26.03 (x64) : Copyright (c) 1999-2026 Igor Pavlov : 2026-09-03
 mt1 d18
Compiler:  CLANG 24.0.0 ver:Clang 24.0.0git (https://github.com/llvm/llvm-project.git dff64a2bf54d0abfc3c2232abb04ec28c40087ed) GCC 4.2.1 : AVX2
Windows 10.0 26100 : Microsoft Hv : Hv#1 : 10.0.26100.33.0.33438
x64 19.1101 threads:4 128TB f:100007F310E2774C
AMD EPYC 9V74 80-Core Processor
(A10F11 : AMD64 Family 25 Model 17 Stepping 1) (->) 2596 MHz
1T CPU Freq (MHz):  3666  3658  3664  3639  3657  3663  3657
RAM size:   16378 MB,  # CPU hardware threads:   4
RAM usage:      6 MB,  # Benchmark threads:      1
```

Rounds: LZMA 7, `-mm=*` 2, JNI 2 (interleaved, rotating order); numbers are medians (JNI: best). Ratios are relative to `gcc17-base`.

#### Builds

| build | compiler | flags |
|---|---|---|
| clang-nightly-avx2 | clang version 24.0.0git (https://github.com/llvm/llvm-project.git dff64a2bf54d0abfc3c2232abb04ec28c40087ed) | `-O3 -march=x86-64-v3 -ffast-math` |
| clang-nightly-avx2-lto | clang version 24.0.0git (https://github.com/llvm/llvm-project.git dff64a2bf54d0abfc3c2232abb04ec28c40087ed) | `-O3 -march=x86-64-v3 -ffast-math -flto` |
| clang-nightly-base | clang version 24.0.0git (https://github.com/llvm/llvm-project.git dff64a2bf54d0abfc3c2232abb04ec28c40087ed) | `(project defaults: -O2, generic x86-64)` |
| gcc17-avx2 | x86_64-w64-mingw32-gcc (sevenzipjbinding CI cross, gcc-17-20261011) 17.0.0 20261011 (experimental) | `-O3 -march=x86-64-v3 -ffast-math` |
| gcc17-avx2-lto | x86_64-w64-mingw32-gcc (sevenzipjbinding CI cross, gcc-17-20261011) 17.0.0 20261011 (experimental) | `-O3 -march=x86-64-v3 -ffast-math -flto=auto` |
| gcc17-base | x86_64-w64-mingw32-gcc (sevenzipjbinding CI cross, gcc-17-20261011) 17.0.0 20261011 (experimental) | `(project defaults: -O2, generic x86-64)` |

#### LZMA rating (7zz b -md22), MIPS - higher is better (1T pinned to one core)

| build | 1T compress | 1T decompress | 1T total | vs base | NT compress | NT decompress | NT total | vs base |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| clang-nightly-avx2 | 4700 | 4731 | 4717 | 0.929 | 20155 | 9842 | 15063 | 0.812 |
| clang-nightly-avx2-lto | 5549 | 4741 | 5149 | 1.014 | 20438 | 15136 | 17717 | 0.955 |
| clang-nightly-base | 5507 | 4679 | 5063 | 0.997 | 20635 | 15482 | 18099 | 0.975 |
| gcc17-avx2 | 6128 | 4784 | 5469 | 1.077 | 20046 | 9126 | 14711 | 0.793 |
| gcc17-avx2-lto | 4979 | 4749 | 4847 | 0.954 | 20155 | 15437 | 17891 | 0.964 |
| gcc17-base | 5265 | 4848 | 5080 | 1.000 | 20997 | 16364 | 18557 | 1.000 |

#### Overall (geometric mean of all `-mm=*` method speeds, single thread) vs base

| rank | build | score |
|---:|---|---:|
| 1 | clang-nightly-base | 1.005 |
| 2 | gcc17-avx2-lto | 1.005 |
| 3 | gcc17-base | 1.000 |
| 4 | gcc17-avx2 | 0.994 |
| 5 | clang-nightly-avx2-lto | 0.994 |
| 6 | clang-nightly-avx2 | 0.979 |

#### Per-method speed, single thread (MB/s; `(dec)` = decode) - higher is better

| method | clang-nightly-avx2 | clang-nightly-avx2-lto | clang-nightly-base | gcc17-avx2 | gcc17-avx2-lto | gcc17-base |
|---|---:|---:|---:|---:|---:|---:|
| LZMA:x1 | 28.9 | 28.8 | **29.2** | 27.1 | 27.3 | 27.5 |
| LZMA:x1 (dec) | 56.9 | 57.5 | 56.4 | 57.7 | 57.7 | **59.3** |
| LZMA:x3 | 11.7 | 10.6 | 11.7 | 10.0 | **12.9** | 10.6 |
| LZMA:x3 (dec) | 54.7 | 55.1 | 54.3 | 55.3 | 55.4 | **56.6** |
| LZMA:x5:mt1 | 4.5 | 4.5 | 4.5 | 4.3 | **4.6** | 4.6 |
| LZMA:x5:mt1 (dec) | 53.9 | 54.2 | 53.8 | 54.3 | 54.9 | **56.0** |
| LZMA:x5:mt2 | 13.4 | 14.5 | 14.5 | 13.9 | 14.3 | **14.5** |
| LZMA:x5:mt2 (dec) | 54.0 | 54.3 | 53.8 | 54.5 | 54.8 | **55.8** |
| Deflate:x1 | 67.8 | **70.4** | 69.7 | 66.4 | 66.5 | 68.7 |
| Deflate:x1 (dec) | 216.9 | **225.6** | 220.8 | 219.5 | 222.2 | 217.6 |
| Deflate:x5 | 21.4 | **22.6** | 21.3 | 20.9 | 22.0 | 21.5 |
| Deflate:x5 (dec) | 218.9 | **226.6** | 221.4 | 220.6 | 223.7 | 217.9 |
| Deflate:x7 | 9.0 | **9.5** | 8.7 | 8.7 | 9.2 | 9.1 |
| Deflate:x7 (dec) | 219.7 | **227.6** | 222.3 | 221.6 | 224.1 | 218.1 |
| Deflate64:x5 | 19.4 | **20.3** | 19.3 | 18.8 | 20.0 | 19.4 |
| Deflate64:x5 (dec) | 219.0 | **226.5** | 220.7 | 221.8 | 223.1 | 218.7 |
| BZip2:x1 | 13.2 | 13.3 | 13.1 | 13.2 | 13.3 | **13.4** |
| BZip2:x1 (dec) | 52.3 | 56.4 | 51.9 | 58.8 | 58.0 | **59.4** |
| BZip2:x5 | 11.8 | 11.7 | **11.8** | 11.8 | 11.8 | 11.7 |
| BZip2:x5 (dec) | 39.0 | 41.1 | 38.6 | **42.9** | 42.4 | 42.8 |
| BZip2:x5:mt2 | 21.0 | 22.2 | 22.4 | 22.4 | **22.7** | 22.5 |
| BZip2:x5:mt2 (dec) | 58.6 | 69.1 | 61.6 | 72.4 | 70.9 | **73.2** |
| BZip2:x7 | 3.8 | 3.8 | **3.8** | 3.6 | 3.7 | 3.7 |
| BZip2:x7 (dec) | 39.3 | 42.0 | 39.0 | 43.1 | 42.5 | **43.3** |
| PPMD:x1 | 8.1 | 8.4 | **8.6** | 8.6 | 8.5 | 8.5 |
| PPMD:x1 (dec) | 7.4 | 7.6 | **8.2** | 7.7 | 7.7 | 7.7 |
| PPMD:x5 | 5.9 | 5.8 | **6.1** | 6.0 | 6.1 | 5.8 |
| PPMD:x5 (dec) | 5.4 | 5.3 | **5.8** | 5.5 | 5.7 | 5.1 |
| Swap4 | 104767.7 | 105718.1 | 105634.4 | **107727.6** | 107219.1 | 107209.0 |
| Swap4 (dec) | 106411.5 | 106969.7 | 107527.6 | 108125.8 | **108301.2** | 108117.1 |
| Delta:4 | 3334.6 | 3358.5 | 3372.4 | **4582.8** | 4577.6 | 4545.6 |
| Delta:4 (dec) | 1882.8 | 1893.4 | 1942.2 | **2097.8** | 2096.6 | 2093.5 |
| BCJ | 4143.8 | 4276.2 | **4323.4** | 3345.5 | 4285.6 | 3348.3 |
| BCJ (dec) | 4014.2 | 4177.6 | 3791.0 | 4318.6 | 4285.5 | **4341.9** |
| ARM64 | 6105.9 | 6069.9 | 6600.0 | 6833.6 | **6844.2** | 6820.0 |
| ARM64 (dec) | 6162.1 | 6050.6 | 6765.1 | **6852.7** | 6770.6 | 6833.8 |
| RISCV | 6363.5 | 6463.4 | **6466.1** | 4623.0 | 4631.0 | 4600.0 |
| RISCV (dec) | 6354.8 | 6444.6 | **6472.4** | 3547.3 | 3455.1 | 4617.7 |
| AES256CBC:1 | 168.3 | 168.6 | 232.9 | 233.1 | 227.3 | **235.1** |
| AES256CBC:1 (dec) | 178.8 | 179.4 | **254.4** | 226.6 | 221.2 | 227.0 |
| AES256CBC:2 | 985.5 | 985.6 | 986.3 | 987.2 | **987.3** | 984.6 |
| AES256CBC:2 (dec) | 7809.4 | 7855.7 | 7905.2 | **7964.1** | 7826.9 | 7938.0 |
| AES256CBC:3 | 982.7 | 986.0 | 986.2 | **987.3** | 984.7 | 983.9 |
| AES256CBC:3 (dec) | 7838.3 | 7865.8 | 7943.9 | 7938.6 | 7886.8 | **7946.1** |
| CRC32:12 | 3732.9 | 3771.7 | **3807.3** | 3505.8 | 3443.5 | 3516.3 |
| CRC64 | 2562.7 | 2641.9 | **2683.9** | 2545.1 | 2526.9 | 2543.9 |
| XXH64 | 9604.8 | 9550.4 | 14107.9 | 10542.4 | 10509.5 | **14136.7** |
| MD5 | 608.9 | 619.2 | 593.4 | **744.3** | 743.0 | 709.5 |
| SHA1:1 | 584.2 | 585.4 | 682.4 | **790.2** | 771.0 | 675.5 |
| SHA1:2 | 1887.2 | 1887.3 | **1887.7** | 1851.2 | 1851.2 | 1840.9 |
| SHA256:1 | 343.4 | 341.9 | 328.5 | **367.8** | 358.2 | 340.0 |
| SHA256:2 | 1770.1 | **1771.4** | 1770.5 | 1765.8 | 1765.7 | 1770.2 |
| SHA512:1 | 543.7 | 542.9 | 516.2 | **572.2** | 570.3 | 537.0 |
| SHA3-256 | 517.3 | 514.8 | 417.7 | 518.3 | **519.2** | 436.4 |
| BLAKE2sp:1 | 517.6 | 491.3 | 477.7 | **525.2** | 524.1 | 515.8 |
| BLAKE2sp:2 | 1518.3 | 1517.5 | **1524.4** | 1417.1 | 1420.1 | 1379.1 |
| BLAKE2sp:3 | 2907.2 | **2908.6** | 2695.7 | 2114.9 | 1982.9 | 2190.2 |

#### JNI binding (JniBench, 32 MiB corpus cap), best time ms - lower is better

| case | clang-nightly-avx2 | clang-nightly-avx2-lto | clang-nightly-base | gcc17-avx2 | gcc17-avx2-lto | gcc17-base |
|---|---:|---:|---:|---:|---:|---:|
| 7z-lzma2-l5-mt1 compress | 9145 | 9014 | 8981 | 8860 | 8800 | **8600** |
| 7z-lzma2-l5-mt1 extract | 307 | 302 | 302 | 302 | 302 | **294** |
| 7z-lzma2-l5-mtN compress | 4940 | **4812** | 4995 | 4905 | 4840 | 4823 |
| 7z-lzma2-l5-mtN extract | 297 | 297 | 296 | 297 | 298 | **293** |
| zip-deflate-l5 compress | 945 | **927** | 951 | 949 | 952 | 942 |
| zip-deflate-l5 extract | 136 | **133** | 135 | 140 | 138 | 138 |
| bzip2-l9-mt1 compress | 7340 | **7293** | 7658 | 7973 | 8049 | 7993 |
| bzip2-l9-mt1 extract | 346 | 342 | 351 | 326 | **326** | 326 |

JNI score (geomean speed vs base): clang-nightly-avx2-lto 1.001, gcc17-base 1.000, gcc17-avx2-lto 0.990, gcc17-avx2 0.987, clang-nightly-avx2 0.987, clang-nightly-base 0.983


## Appendix B: full local results (AMD Ryzen 5 5500U, Zen 2)


```
7-Zip (z) 26.03 (x64) : Copyright (c) 1999-2026 Igor Pavlov : 2026-09-03
 mt1 d18
Compiler:  CLANG 24.0.0 ver:Clang 24.0.0git (https://github.com/llvm/llvm-project.git dff64a2bf54d0abfc3c2232abb04ec28c40087ed) GCC 4.2.1 : AVX2
Windows 10.0 19044
x64 17.6801 threads:12 128TB f:1FB10F2774C
AMD Ryzen 5 5500U with Radeon Graphics
(860F81 : AMD64 Family 23 Model 104 Stepping 1) (8608103.0->8608103.0) 2096 MHz
1T CPU Freq (MHz):  4013  4016  4021  3995  4013  4012  4010
RAM size:   32139 MB,  # CPU hardware threads:  12
RAM usage:      6 MB,  # Benchmark threads:      1
```

Rounds: LZMA 5, `-mm=*` 1, JNI 2 (interleaved, rotating order); numbers are medians (JNI: best). Ratios are relative to `gcc17-base`.

#### Builds

| build | compiler | flags |
|---|---|---|
| clang-nightly-avx2 | clang version 24.0.0git (https://github.com/llvm/llvm-project.git dff64a2bf54d0abfc3c2232abb04ec28c40087ed) | `-O3 -march=x86-64-v3 -ffast-math` |
| clang-nightly-avx2-lto | clang version 24.0.0git (https://github.com/llvm/llvm-project.git dff64a2bf54d0abfc3c2232abb04ec28c40087ed) | `-O3 -march=x86-64-v3 -ffast-math -flto` |
| clang-nightly-base | clang version 24.0.0git (https://github.com/llvm/llvm-project.git dff64a2bf54d0abfc3c2232abb04ec28c40087ed) | `(project defaults: -O2, generic x86-64)` |
| gcc17-avx2 | x86_64-w64-mingw32-gcc (sevenzipjbinding CI cross, gcc-17-20261011) 17.0.0 20261011 (experimental) | `-O3 -march=x86-64-v3 -ffast-math` |
| gcc17-avx2-lto | x86_64-w64-mingw32-gcc (sevenzipjbinding CI cross, gcc-17-20261011) 17.0.0 20261011 (experimental) | `-O3 -march=x86-64-v3 -ffast-math -flto=auto` |
| gcc17-base | x86_64-w64-mingw32-gcc (sevenzipjbinding CI cross, gcc-17-20261011) 17.0.0 20261011 (experimental) | `(project defaults: -O2, generic x86-64)` |

#### LZMA rating (7zz b -md22), MIPS - higher is better (1T pinned to one core)

| build | 1T compress | 1T decompress | 1T total | vs base | NT compress | NT decompress | NT total | vs base |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| clang-nightly-avx2 | 4587 | 4349 | 4459 | 1.058 | 41126 | 41841 | 41449 | 0.976 |
| clang-nightly-avx2-lto | 4714 | 4376 | 4545 | 1.079 | 41889 | 41627 | 42066 | 0.990 |
| clang-nightly-base | 4480 | 4254 | 4362 | 1.035 | 41076 | 39399 | 40518 | 0.954 |
| gcc17-avx2 | 4479 | 4353 | 4416 | 1.048 | 41867 | 42637 | 42178 | 0.993 |
| gcc17-avx2-lto | 4639 | 4405 | 4519 | 1.072 | 39829 | 42098 | 40964 | 0.964 |
| gcc17-base | 4063 | 4413 | 4214 | 1.000 | 42310 | 42661 | 42485 | 1.000 |

#### Overall (geometric mean of all `-mm=*` method speeds, single thread) vs base

| rank | build | score |
|---:|---|---:|
| 1 | clang-nightly-base | 1.028 |
| 2 | clang-nightly-avx2-lto | 1.020 |
| 3 | gcc17-avx2-lto | 1.011 |
| 4 | gcc17-avx2 | 1.008 |
| 5 | gcc17-base | 1.000 |
| 6 | clang-nightly-avx2 | 0.972 |

#### Per-method speed, single thread (MB/s; `(dec)` = decode) - higher is better

| method | clang-nightly-avx2 | clang-nightly-avx2-lto | clang-nightly-base | gcc17-avx2 | gcc17-avx2-lto | gcc17-base |
|---|---:|---:|---:|---:|---:|---:|
| LZMA:x1 | 22.4 | 25.0 | **26.7** | 23.2 | 23.1 | 23.2 |
| LZMA:x1 (dec) | 52.2 | 53.4 | 52.0 | 53.6 | 53.8 | **54.2** |
| LZMA:x3 | **7.2** | 6.9 | 7.0 | 6.9 | 6.6 | 6.8 |
| LZMA:x3 (dec) | 50.1 | 50.3 | 49.2 | 50.5 | **50.9** | 49.7 |
| LZMA:x5:mt1 | 3.9 | 3.9 | 3.9 | 4.0 | **4.1** | 4.0 |
| LZMA:x5:mt1 (dec) | 49.3 | 49.3 | 47.6 | 49.7 | **50.1** | 50.1 |
| LZMA:x5:mt2 | 11.9 | 11.7 | 11.6 | 11.1 | 12.1 | **12.1** |
| LZMA:x5:mt2 (dec) | 49.5 | 49.5 | 47.4 | 50.0 | 50.1 | **50.3** |
| Deflate:x1 | 68.1 | **69.2** | 68.6 | 66.0 | 67.0 | 67.8 |
| Deflate:x1 (dec) | 214.5 | **214.5** | 214.4 | 206.4 | 207.4 | 206.5 |
| Deflate:x5 | 18.1 | **20.3** | 19.4 | 18.9 | 18.8 | 18.1 |
| Deflate:x5 (dec) | 214.5 | 214.6 | **215.5** | 203.5 | 210.5 | 212.8 |
| Deflate:x7 | 7.7 | **8.3** | 7.5 | 7.1 | 7.8 | 7.5 |
| Deflate:x7 (dec) | 213.6 | 213.4 | **217.1** | 206.4 | 209.5 | 209.3 |
| Deflate64:x5 | 7.0 | **18.3** | 17.4 | 17.0 | 17.6 | 16.7 |
| Deflate64:x5 (dec) | 155.2 | **214.9** | 213.1 | 210.9 | 214.7 | 206.4 |
| BZip2:x1 | 8.7 | 12.6 | **13.2** | 13.2 | 13.1 | 13.0 |
| BZip2:x1 (dec) | 47.2 | 53.7 | 47.5 | 55.4 | 54.5 | **55.6** |
| BZip2:x5 | 10.9 | 10.1 | **11.3** | 9.7 | 10.8 | 10.2 |
| BZip2:x5 (dec) | 30.9 | 34.8 | 32.8 | **37.3** | 36.8 | 36.5 |
| BZip2:x5:mt2 | 16.7 | 16.4 | 17.5 | **19.8** | 16.4 | 16.6 |
| BZip2:x5:mt2 (dec) | 51.1 | 57.3 | 48.3 | **61.6** | 56.9 | 58.5 |
| BZip2:x7 | 3.4 | 3.3 | **3.6** | 3.5 | 3.4 | 3.4 |
| BZip2:x7 (dec) | 32.2 | 37.9 | 32.2 | **40.8** | 36.2 | 38.1 |
| PPMD:x1 | 7.3 | 7.2 | 7.9 | **8.1** | 8.0 | 8.0 |
| PPMD:x1 (dec) | 6.5 | 6.8 | 7.0 | 7.1 | **7.1** | 7.0 |
| PPMD:x5 | 4.4 | 4.5 | 4.7 | 4.8 | **4.9** | 4.7 |
| PPMD:x5 (dec) | 4.0 | 4.2 | **4.3** | 4.3 | 4.3 | 4.3 |
| Swap4 | 100042.1 | 98143.9 | 99498.7 | 98175.1 | 100425.3 | **100563.6** |
| Swap4 (dec) | 93806.1 | 100713.4 | **100858.0** | 99659.8 | 97886.3 | 99114.2 |
| Delta:4 | 3502.6 | 3797.6 | 3801.7 | **3803.5** | 3690.2 | 3730.6 |
| Delta:4 (dec) | 2093.3 | 2139.0 | **2169.2** | 2019.0 | 2016.9 | 1954.9 |
| BCJ | 2748.8 | 2867.6 | 2907.3 | 2441.6 | **3527.2** | 2440.2 |
| BCJ (dec) | 3419.8 | 3432.6 | 3459.6 | 2873.9 | **3471.5** | 2890.7 |
| ARM64 | 5856.0 | 5527.8 | **5889.2** | 4715.1 | 4657.3 | 4730.2 |
| ARM64 (dec) | 5944.7 | **5956.9** | 4348.3 | 4727.5 | 4655.5 | 4710.6 |
| RISCV | 4296.9 | 4478.9 | **4601.3** | 3248.2 | 3163.9 | 3313.3 |
| RISCV (dec) | 4341.3 | 4454.2 | **4455.1** | 3364.5 | 2725.7 | 3271.7 |
| AES256CBC:1 | 188.3 | 187.5 | **260.4** | 239.1 | 238.5 | 237.5 |
| AES256CBC:1 (dec) | 190.5 | 190.9 | **264.6** | 228.7 | 227.7 | 227.2 |
| AES256CBC:2 | 1058.5 | 1077.2 | 1078.6 | 1077.1 | **1079.5** | 1079.0 |
| AES256CBC:2 (dec) | 7182.2 | **7212.5** | 7185.3 | 7173.3 | 7167.3 | 7181.7 |
| CRC32:12 | 4088.9 | **4199.8** | 4198.6 | 3792.0 | 3841.3 | 3800.1 |
| CRC64 | 2889.7 | 2912.4 | **3010.0** | 2849.1 | 2837.2 | 2842.4 |
| XXH64 | 9636.6 | 9660.2 | **15679.2** | 10404.9 | 10386.1 | 15672.4 |
| MD5 | 671.7 | 675.8 | 650.2 | **766.2** | 760.5 | 737.3 |
| SHA1:1 | 576.4 | 579.6 | 678.0 | **799.1** | 793.7 | 671.8 |
| SHA1:2 | 2076.3 | 2076.6 | **2080.6** | 1965.7 | 1949.5 | 1921.0 |
| SHA256:1 | 329.9 | 329.5 | 330.1 | **363.5** | 359.4 | 328.0 |
| SHA256:2 | 1950.7 | 1949.3 | 1951.2 | 1949.4 | 1925.7 | **1951.2** |
| SHA512:1 | 543.8 | 540.7 | 518.9 | **560.4** | 555.5 | 516.3 |
| SHA3-256 | **488.0** | 485.4 | 378.1 | 481.9 | 485.5 | 407.3 |
| BLAKE2sp:1 | 497.2 | 471.5 | 493.5 | **512.0** | 509.3 | 498.7 |
| BLAKE2sp:2 | **1678.7** | 1652.1 | 1581.8 | 1497.2 | 1503.3 | 1514.5 |
| BLAKE2sp:3 | **3242.0** | 3234.5 | 2828.9 | 2421.3 | 2481.5 | 2423.7 |

#### JNI binding (JniBench, 32 MiB corpus cap), best time ms - lower is better

| case | clang-nightly-avx2 | clang-nightly-avx2-lto | clang-nightly-base | gcc17-avx2 | gcc17-avx2-lto | gcc17-base |
|---|---:|---:|---:|---:|---:|---:|
| 7z-lzma2-l5-mt1 compress | 11346 | 11353 | 11386 | 11210 | 11239 | **11154** |
| 7z-lzma2-l5-mt1 extract | 340 | **336** | 340 | 344 | 339 | 341 |
| 7z-lzma2-l5-mtN compress | 6364 | **6114** | 6328 | 6285 | 6272 | 6119 |
| 7z-lzma2-l5-mtN extract | 339 | **330** | 334 | 336 | 341 | 337 |
| zip-deflate-l5 compress | 541 | **522** | 533 | 544 | 544 | 545 |
| zip-deflate-l5 extract | **147** | 148 | 150 | 152 | 151 | 154 |
| bzip2-l9-mt1 compress | 3220 | 3205 | **3162** | 3502 | 3384 | 3436 |
| bzip2-l9-mt1 extract | 443 | **411** | 457 | 427 | 428 | 427 |

JNI score (geomean speed vs base): clang-nightly-avx2-lto 1.027, clang-nightly-base 1.003, clang-nightly-avx2 1.003, gcc17-base 1.000, gcc17-avx2-lto 0.999, gcc17-avx2 0.994

## Appendix C: stable compilers run (AMD EPYC 7763, Zen 3)


```
7-Zip (z) 26.03 (x64) : Copyright (c) 1999-2026 Igor Pavlov : 2026-09-03
 mt1 d18
Compiler:  CLANG 24.0.0 ver:Clang 24.0.0git (https://github.com/llvm/llvm-project.git dff64a2bf54d0abfc3c2232abb04ec28c40087ed) GCC 4.2.1 : AVX2
Windows 10.0 26100 : Microsoft Hv : Hv#1 : 10.0.26100.33.0.33438
x64 19.101 threads:4 128TB f:100005F310E2774C
AMD EPYC 7763 64-Core Processor
(A00F11 : AMD64 Family 25 Model 1 Stepping 1) (->) 2445 MHz
1T CPU Freq (MHz):  3200  3205  3211  3211  3191  3207  3207
RAM size:   16378 MB,  # CPU hardware threads:   4
RAM usage:      6 MB,  # Benchmark threads:      1
```

Rounds: LZMA 7, `-mm=*` 2, JNI 2 (interleaved, rotating order); numbers are medians (JNI: best). Ratios are relative to `gcc16-base`.

#### Builds

| build | compiler | flags |
|---|---|---|
| clang-nightly-avx2-lto | clang version 24.0.0git (https://github.com/llvm/llvm-project.git dff64a2bf54d0abfc3c2232abb04ec28c40087ed) | `-O3 -march=x86-64-v3 -ffast-math -flto` |
| clang23-avx2 | clang version 23.1.3 (https://github.com/llvm/llvm-project.git 0d261d1ca552c95a8f007e061c787ac7132fbcbc) | `-O3 -march=x86-64-v3 -ffast-math` |
| clang23-avx2-lto | clang version 23.1.3 (https://github.com/llvm/llvm-project.git 0d261d1ca552c95a8f007e061c787ac7132fbcbc) | `-O3 -march=x86-64-v3 -ffast-math -flto` |
| clang23-base | clang version 23.1.3 (https://github.com/llvm/llvm-project.git 0d261d1ca552c95a8f007e061c787ac7132fbcbc) | `(project defaults: -O2, generic x86-64)` |
| gcc16-avx2 | x86_64-w64-mingw32-gcc (sevenzipjbinding CI cross, gcc-16.2.0) 16.2.0 | `-O3 -march=x86-64-v3 -ffast-math` |
| gcc16-avx2-lto | x86_64-w64-mingw32-gcc (sevenzipjbinding CI cross, gcc-16.2.0) 16.2.0 | `-O3 -march=x86-64-v3 -ffast-math -flto=auto` |
| gcc16-base | x86_64-w64-mingw32-gcc (sevenzipjbinding CI cross, gcc-16.2.0) 16.2.0 | `(project defaults: -O2, generic x86-64)` |
| gcc17-avx2-lto | x86_64-w64-mingw32-gcc (sevenzipjbinding CI cross, gcc-17-20261011) 17.0.0 20261011 (experimental) | `-O3 -march=x86-64-v3 -ffast-math -flto=auto` |

#### LZMA rating (7zz b -md22), MIPS - higher is better (1T pinned to one core)

| build | 1T compress | 1T decompress | 1T total | vs base | NT compress | NT decompress | NT total | vs base |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| clang-nightly-avx2-lto | 4866 | 4013 | 4450 | 1.005 | 16206 | 13335 | 14760 | 0.977 |
| clang23-avx2 | 4821 | 4035 | 4376 | 0.988 | 16474 | 13364 | 14907 | 0.986 |
| clang23-avx2-lto | 5204 | 4012 | 4609 | 1.041 | 16635 | 13092 | 14891 | 0.985 |
| clang23-base | 4600 | 4032 | 4308 | 0.973 | 16609 | 13275 | 14912 | 0.987 |
| gcc16-avx2 | 4549 | 4082 | 4312 | 0.974 | 16504 | 13699 | 15101 | 0.999 |
| gcc16-avx2-lto | 5036 | 4098 | 4575 | 1.033 | 16190 | 13573 | 14899 | 0.986 |
| gcc16-base | 4783 | 4071 | 4427 | 1.000 | 16711 | 13502 | 15113 | 1.000 |
| gcc17-avx2-lto | 4916 | 4017 | 4438 | 1.002 | 15936 | 13474 | 14705 | 0.973 |

#### Overall (geometric mean of all `-mm=*` method speeds, single thread) vs base

| rank | build | score |
|---:|---|---:|
| 1 | clang23-base | 1.014 |
| 2 | clang-nightly-avx2-lto | 1.010 |
| 3 | clang23-avx2-lto | 1.009 |
| 4 | gcc16-avx2 | 1.007 |
| 5 | clang23-avx2 | 1.005 |
| 6 | gcc16-avx2-lto | 1.003 |
| 7 | gcc16-base | 1.000 |
| 8 | gcc17-avx2-lto | 0.999 |

#### Per-method speed, single thread (MB/s; `(dec)` = decode) - higher is better

| method | clang-nightly-avx2-lto | clang23-avx2 | clang23-avx2-lto | clang23-base | gcc16-avx2 | gcc16-avx2-lto | gcc16-base | gcc17-avx2-lto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LZMA:x1 | **24.0** | 23.9 | 23.6 | 23.7 | 21.9 | 22.5 | 23.0 | 22.4 |
| LZMA:x1 (dec) | 48.5 | 48.5 | 47.9 | 48.0 | 49.3 | 49.3 | **49.4** | 48.6 |
| LZMA:x3 | 7.6 | 7.4 | 7.3 | **8.2** | 6.6 | 7.0 | 6.7 | 6.8 |
| LZMA:x3 (dec) | 45.9 | 45.8 | 45.1 | 45.6 | 46.3 | **46.7** | 46.4 | 46.2 |
| LZMA:x5:mt1 | 3.7 | 3.8 | **3.9** | 3.8 | 3.6 | 3.5 | 3.7 | 3.7 |
| LZMA:x5:mt1 (dec) | 44.9 | **45.9** | 45.7 | 45.4 | 45.8 | 45.8 | 45.7 | 45.3 |
| LZMA:x5:mt2 | 11.2 | 11.1 | 10.7 | 10.6 | 10.5 | 10.8 | **11.3** | 11.0 |
| LZMA:x5:mt2 (dec) | 45.5 | **46.2** | 45.1 | 45.6 | 45.9 | 45.9 | 45.7 | 45.2 |
| Deflate:x1 | 60.3 | 59.0 | **61.3** | 59.0 | 55.8 | 57.0 | 57.7 | 56.5 |
| Deflate:x1 (dec) | 193.2 | 189.5 | 194.2 | 188.0 | 191.6 | **194.2** | 185.0 | 191.0 |
| Deflate:x5 | 18.7 | 18.0 | **18.8** | 17.7 | 17.6 | 18.8 | 18.2 | 18.5 |
| Deflate:x5 (dec) | 192.9 | 188.7 | **194.8** | 187.5 | 192.1 | 194.8 | 184.2 | 191.7 |
| Deflate:x7 | 7.3 | 7.4 | 7.5 | 7.2 | 7.3 | **7.6** | 7.4 | 7.6 |
| Deflate:x7 (dec) | 193.7 | 188.0 | **197.2** | 190.1 | 193.5 | 195.8 | 185.9 | 193.3 |
| Deflate64:x5 | 16.8 | 16.2 | 16.7 | 16.0 | 15.9 | **16.9** | 16.4 | 16.7 |
| Deflate64:x5 (dec) | 191.2 | 185.9 | 194.8 | 189.0 | 193.8 | **195.1** | 186.7 | 193.9 |
| BZip2:x1 | 11.0 | 11.0 | 11.1 | 11.0 | 11.3 | 11.0 | **11.3** | 11.1 |
| BZip2:x1 (dec) | 44.0 | 41.7 | 44.0 | 42.4 | **46.8** | 45.7 | 46.1 | 45.4 |
| BZip2:x5 | **10.1** | 9.8 | 9.8 | 10.0 | 10.0 | 9.7 | 10.0 | 9.9 |
| BZip2:x5 (dec) | 30.8 | 29.9 | 31.6 | 30.8 | 31.8 | **32.0** | 30.8 | 29.4 |
| BZip2:x5:mt2 | 18.9 | 17.0 | 17.1 | 15.9 | **19.0** | 18.6 | 18.8 | 18.5 |
| BZip2:x5:mt2 (dec) | 52.7 | 46.7 | 50.8 | 47.9 | **55.5** | 54.5 | 54.7 | 52.5 |
| BZip2:x7 | **3.1** | 3.1 | 3.0 | 3.1 | 3.1 | 3.1 | 3.1 | 3.0 |
| BZip2:x7 (dec) | 30.6 | 30.1 | 31.6 | 31.0 | **32.4** | 31.5 | 32.1 | 29.0 |
| PPMD:x1 | 6.7 | 6.2 | 6.6 | 6.6 | **7.2** | 7.1 | 7.1 | 7.0 |
| PPMD:x1 (dec) | 5.8 | 6.3 | 6.3 | 6.4 | 6.1 | **6.4** | 6.3 | 6.4 |
| PPMD:x5 | 4.4 | 4.1 | 4.4 | 4.6 | 4.6 | **4.7** | 4.4 | 4.3 |
| PPMD:x5 (dec) | 4.0 | 4.1 | 4.2 | **4.2** | 4.0 | 4.1 | 4.1 | 4.0 |
| Swap4 | **83324.8** | 81685.8 | 80754.2 | 82402.1 | 82450.4 | 79710.4 | 82192.2 | 82106.8 |
| Swap4 (dec) | 82354.0 | 82250.5 | 81153.0 | 81355.9 | **82408.7** | 80025.5 | 81869.0 | 81913.1 |
| Delta:4 | 3072.0 | 3038.2 | 2878.7 | 3022.8 | **3323.4** | 3237.1 | 3298.4 | 3308.1 |
| Delta:4 (dec) | 1739.6 | 1731.0 | 1715.3 | **1740.5** | 1417.4 | 1397.3 | 1417.1 | 1416.3 |
| BCJ | 3108.8 | 3188.8 | 3086.7 | 3167.1 | 2590.0 | 3016.9 | 2597.3 | **3277.2** |
| BCJ (dec) | 3169.9 | **3340.4** | 3046.5 | 3262.6 | 3213.9 | 3124.1 | 3202.2 | 3285.0 |
| ARM64 | 5049.8 | **5299.3** | 4769.3 | 4535.4 | 4703.5 | 4531.3 | 4704.5 | 4693.9 |
| ARM64 (dec) | **5146.5** | 4996.9 | 5033.7 | 4582.6 | 4735.6 | 4512.9 | 4732.3 | 4703.0 |
| RISCV | 4226.9 | **4253.1** | 4059.6 | 4238.6 | 3139.4 | 2451.2 | 3119.2 | 3145.9 |
| RISCV (dec) | 4331.5 | 4193.3 | **4405.3** | 4166.9 | 2570.3 | 2967.8 | 3106.2 | 2589.4 |
| AES256CBC:1 | 150.9 | 149.6 | 145.6 | **214.3** | 200.2 | 195.9 | 200.2 | 200.3 |
| AES256CBC:1 (dec) | 165.2 | 165.4 | 165.2 | **221.8** | 198.0 | 189.5 | 196.9 | 198.2 |
| AES256CBC:2 | 863.4 | 862.5 | 860.6 | 862.7 | **864.5** | 863.2 | 862.6 | 864.5 |
| AES256CBC:2 (dec) | 6715.2 | **6737.3** | 6700.7 | 6551.4 | 6624.2 | 6575.0 | 6598.0 | 6608.8 |
| AES256CBC:3 | 863.1 | 863.5 | 862.3 | 862.0 | 864.1 | **864.1** | 863.0 | 864.0 |
| AES256CBC:3 (dec) | 6737.6 | 6741.0 | **6747.9** | 6554.2 | 6599.8 | 6559.2 | 6624.2 | 6631.6 |
| CRC32:12 | 3281.4 | **3320.7** | 3287.9 | 3295.6 | 3041.3 | 3063.6 | 3080.9 | 3060.7 |
| CRC64 | 2322.6 | 2350.0 | 2148.2 | **2352.6** | 2218.8 | 2242.2 | 2236.3 | 2234.5 |
| XXH64 | 7587.9 | 7586.6 | 7612.7 | 12240.3 | 12345.4 | **12354.0** | 12346.0 | 8100.3 |
| MD5 | 540.2 | 530.7 | 533.6 | 520.6 | **648.5** | 647.3 | 620.7 | 648.3 |
| SHA1:1 | 497.4 | 583.3 | 598.9 | 577.0 | **675.9** | 611.0 | 561.4 | 668.3 |
| SHA1:2 | 1651.7 | 1649.7 | **1652.3** | 1651.9 | 1613.8 | 1626.9 | 1620.0 | 1649.0 |
| SHA256:1 | 275.4 | 278.3 | 289.4 | 281.9 | 307.5 | **308.8** | 292.2 | 306.0 |
| SHA256:2 | 1545.5 | 1547.1 | 1548.6 | 1547.2 | **1549.5** | 1548.1 | 1548.2 | 1548.8 |
| SHA512:1 | 443.2 | 451.8 | 459.8 | 435.6 | **489.2** | 484.1 | 458.7 | 455.6 |
| SHA3-256 | 445.4 | 434.7 | 444.2 | 365.3 | **452.6** | 428.7 | 381.7 | 436.6 |
| BLAKE2sp:1 | 416.9 | 434.0 | 440.5 | 454.2 | 453.8 | 454.4 | 451.9 | **464.1** |
| BLAKE2sp:2 | 1421.0 | 1412.9 | **1422.1** | 1318.1 | 1332.6 | 1334.7 | 1279.9 | 1332.3 |
| BLAKE2sp:3 | 2727.6 | **2885.4** | 2808.7 | 2201.7 | 1974.6 | 1817.7 | 1901.8 | 1904.1 |

#### JNI binding (JniBench, 32 MiB corpus cap), best time ms - lower is better

| case | clang-nightly-avx2-lto | clang23-avx2 | clang23-avx2-lto | clang23-base | gcc16-avx2 | gcc16-avx2-lto | gcc16-base | gcc17-avx2-lto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 7z-lzma2-l5-mt1 compress | 10782 | 10012 | **9983** | 10182 | 10363 | 10423 | 10674 | 10420 |
| 7z-lzma2-l5-mt1 extract | 356 | 352 | 354 | 355 | **349** | 351 | 358 | 361 |
| 7z-lzma2-l5-mtN compress | 5758 | **5455** | 5620 | 6024 | 6069 | 5875 | 5624 | 5741 |
| 7z-lzma2-l5-mtN extract | 352 | 349 | 352 | 348 | 345 | **343** | 349 | 356 |
| zip-deflate-l5 compress | **1166** | 1218 | 1197 | 1180 | 1178 | 1187 | 1174 | 1202 |
| zip-deflate-l5 extract | 158 | 160 | **155** | 163 | 161 | 160 | 167 | 161 |
| bzip2-l9-mt1 compress | 9076 | 8990 | 9140 | **8909** | 9609 | 9220 | 9876 | 9977 |
| bzip2-l9-mt1 extract | 439 | 441 | 431 | 434 | **420** | 430 | 424 | 431 |

JNI score (geomean speed vs base): clang23-avx2-lto 1.024, clang23-avx2 1.022, gcc16-avx2-lto 1.013, clang23-base 1.011, clang-nightly-avx2-lto 1.010, gcc16-avx2 1.008, gcc16-base 1.000, gcc17-avx2-lto 0.995

