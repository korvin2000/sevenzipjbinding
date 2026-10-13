#!/usr/bin/env bash
# Cross-build (Linux host -> Windows x64) the 7-Zip-JBinding DLL/jars and 7-Zip's own console 7zz.exe
# (same 7zip/ sources, C code paths only - the JNI build uses no asm either) with one compiler + one
# optimization variant. Used by .github/workflows/windows-x64-compilers.yml.
#
# Usage: build-variant.sh <gcc|clang> <base|avx2|avx2-lto> <out-dir>
#   x86_64-w64-mingw32-{gcc,g++|clang,clang++,windres} must be on PATH; JAVA_HOME = Linux JDK 8.
# Variants:
#   base      project defaults (-O2, generic x86-64) = what the release builds use
#   avx2      -O3 -march=x86-64-v3 (AVX2/FMA/BMI2, Haswell+/Zen+) -ffast-math
#   avx2-lto  avx2 + link-time optimization
set -euo pipefail

CC_KIND=$1
VARIANT=$2
OUT=$(mkdir -p "$3" && cd "$3" && pwd)
SRC=$(cd "$(dirname "$0")/../.." && pwd)
WORK=$(dirname "$OUT")/work-$(basename "$OUT")   # build trees stay out of the uploaded OUT dir
T=x86_64-w64-mingw32

case $CC_KIND in
    gcc)   CC=$T-gcc;   CXX=$T-g++;     LTO=-flto=auto ;;
    clang) CC=$T-clang; CXX=$T-clang++; LTO=-flto ;;
    *) echo "unknown compiler kind: $CC_KIND" >&2; exit 2 ;;
esac
case $VARIANT in
    base)     OPT="";  PERF="" ;;
    avx2)     OPT=-O3; PERF="-O3 -march=x86-64-v3 -ffast-math" ;;
    avx2-lto) OPT=-O3; PERF="-O3 -march=x86-64-v3 -ffast-math $LTO" ;;
    *) echo "unknown variant: $VARIANT" >&2; exit 2 ;;
esac

# A Windows JNI build needs the Windows jni_md.h (LLP64: jlong = __int64; the Linux one makes jlong a
# 64-bit 'long', which is 32-bit on Windows). FindJavaExtended.cmake looks in include/win32 first, so
# overlay a copy of the Linux JDK with it (content as in the Windows JDK 8).
JDK=$(dirname "$OUT")/jdk-win-jni
if [ ! -f "$JDK/include/win32/jni_md.h" ]; then
    rm -rf "$JDK" && cp -a "$JAVA_HOME" "$JDK" && mkdir -p "$JDK/include/win32"
    cat > "$JDK/include/win32/jni_md.h" <<'EOF'
#ifndef _JAVASOFT_JNI_MD_H_
#define _JAVASOFT_JNI_MD_H_
#define JNIEXPORT __declspec(dllexport)
#define JNIIMPORT __declspec(dllimport)
#define JNICALL __stdcall
typedef long jint;
typedef __int64 jlong;
typedef signed char jbyte;
#endif
EOF
fi

echo "::group::JNI DLL ($CC_KIND $VARIANT)"
B=$WORK/build
rm -rf "$WORK" && mkdir -p "$B"
cmake -S "$SRC" -B "$B" -G Ninja \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DCMAKE_SYSTEM_NAME=Windows -DCMAKE_SYSTEM_PROCESSOR=AMD64 \
    -DMINGW64=Yes -DJAVA_SYSTEM=Windows -DJAVA_ARCH=amd64 \
    -DCMAKE_C_COMPILER=$CC -DCMAKE_CXX_COMPILER=$CXX -DCMAKE_RC_COMPILER=$T-windres \
    -DCMAKE_SHARED_LINKER_FLAGS=-static \
    -DCMAKE_BUILD_TYPE=Release \
    -DOPTIMIZATION_FLAGS="$OPT" \
    -DCMAKE_C_FLAGS="$PERF" -DCMAKE_CXX_FLAGS="$PERF" \
    -DJAVA_JDK="$JDK" -DJAVA_INCLUDE_PATH2="$JDK/include/win32"
cmake --build "$B" -j"$(nproc)" -v > "$OUT/build-dll.log" 2>&1 || { tail -100 "$OUT/build-dll.log"; exit 1; }
grep -m1 -E 'SevenZipJBinding\.cpp' "$OUT/build-dll.log" > "$OUT/dll-compile-cmd.txt" || true
cmake --build "$B" --target package > /dev/null
echo "::endgroup::"

echo "::group::7zz.exe ($CC_KIND $VARIANT)"
O=$WORK/7zz-obj
# 7zip_gcc.mak hard-codes -O2 in CFLAGS_BASE but appends FLAGS_FLTO (also on the link line) after it;
# CFLAGS_WARN*= drop -Werror/-Weverything (new compilers warn more). Z7_JB_DISABLE_VAES mirrors the DLL.
make -C "$SRC/7zip/CPP/7zip/Bundles/Alone2" -f makefile.gcc -j"$(nproc)" \
    IS_MINGW=1 MSYSTEM=MINGW64 IS_X64=1 O="$O" \
    CC=$CC CXX=$CXX RC=$T-windres \
    CFLAGS_WARN_WALL= CFLAGS_WARN= \
    MY_ARCH=-DZ7_JB_DISABLE_VAES FLAGS_FLTO="$PERF" > "$OUT/build-7zz.log" 2>&1 \
    || { tail -100 "$OUT/build-7zz.log"; exit 1; }
grep -m1 -E 'LzmaEnc\.c' "$OUT/build-7zz.log" > "$OUT/7zz-compile-cmd.txt" || true
echo "::endgroup::"

cp "$O/7zz.exe" "$OUT/"
cp "$(find "$B/jbinding-cpp" -name '*7-Zip-JBinding.dll' | head -1)" "$OUT/"
cp "$B"/sevenzipjbinding-Windows-amd64.jar "$B"/jbinding-java/sevenzipjbinding.jar "$B"/sevenzipjbinding-*-Windows-amd64.zip "$OUT/"
{
    echo "compiler: $($CC --version | head -1)"
    echo "variant:  $VARIANT"
    echo "flags:    ${PERF:-(project defaults: -O2, generic x86-64)}"
} | tee "$OUT/info.txt"
ls -l "$OUT"/*.exe "$OUT"/*.dll "$OUT"/*.jar
