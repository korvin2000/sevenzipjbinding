import java.io.File;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import net.sf.sevenzipjbinding.ArchiveFormat;
import net.sf.sevenzipjbinding.ExtractAskMode;
import net.sf.sevenzipjbinding.ExtractOperationResult;
import net.sf.sevenzipjbinding.IArchiveExtractCallback;
import net.sf.sevenzipjbinding.IInArchive;
import net.sf.sevenzipjbinding.IOutCreateArchive;
import net.sf.sevenzipjbinding.IOutCreateCallback;
import net.sf.sevenzipjbinding.IOutFeatureSetLevel;
import net.sf.sevenzipjbinding.IOutFeatureSetMultithreading;
import net.sf.sevenzipjbinding.IOutItemAllFormats;
import net.sf.sevenzipjbinding.ISequentialInStream;
import net.sf.sevenzipjbinding.ISequentialOutStream;
import net.sf.sevenzipjbinding.SevenZip;
import net.sf.sevenzipjbinding.SevenZipException;
import net.sf.sevenzipjbinding.impl.OutItemFactory;
import net.sf.sevenzipjbinding.util.ByteArrayStream;

/**
 * JNI-level benchmark for .github/workflows/windows-x64-compilers.yml: compresses an in-memory corpus
 * through 7-Zip-JBinding (create archive into a ByteArrayStream) and extracts it again (to a counting
 * sink), so the whole binding path - not just the codec - is timed.
 *
 * Usage: java -cp sevenzipjbinding.jar;sevenzipjbinding-Windows-amd64.jar;. JniBench label reps maxMiB dir...
 * Prints one CSV line per case/op: label,case,op,min_ms,median_ms,MiB_per_s(min),packed_bytes
 */
public class JniBench {
    static final List<String> names = new ArrayList<String>();
    static final List<byte[]> data = new ArrayList<byte[]>();
    static long total;

    public static void main(String[] args) throws Exception {
        String label = args[0];
        int reps = Integer.parseInt(args[1]);
        long max = Long.parseLong(args[2]) << 20;
        for (int i = 3; i < args.length; i++) {
            load(new File(args[i]), max);
        }
        SevenZip.initSevenZipFromPlatformJAR();
        System.err.printf("%s: %d files, %.1f MiB, 7-Zip %s%n", label, names.size(), total / 1048576.0,
                SevenZip.getSevenZipVersion().version);

        run(label, reps, "7z-lzma2-l5-mt1", ArchiveFormat.SEVEN_ZIP, 5, 1, false);
        run(label, reps, "7z-lzma2-l5-mtN", ArchiveFormat.SEVEN_ZIP, 5, 0, false);
        run(label, reps, "zip-deflate-l5", ArchiveFormat.ZIP, 5, 1, false);
        run(label, reps, "bzip2-l9-mt1", ArchiveFormat.BZIP2, 9, 1, true);
    }

    static void load(File f, long max) throws Exception {
        if (f.isDirectory()) {
            File[] list = f.listFiles();
            Arrays.sort(list);
            for (File c : list) {
                load(c, max);
            }
        } else if (f.isFile() && total + f.length() <= max) {
            names.add(f.getPath().replace('\\', '/'));
            data.add(Files.readAllBytes(f.toPath()));
            total += f.length();
        }
    }

    static void run(String label, int reps, String name, ArchiveFormat format, int level, int threads,
            boolean singleBlob) throws Exception {
        final byte[][] items;
        if (singleBlob) {
            byte[] blob = new byte[(int) total];
            int pos = 0;
            for (byte[] d : data) {
                System.arraycopy(d, 0, blob, pos, d.length);
                pos += d.length;
            }
            items = new byte[][] { blob };
        } else {
            items = data.toArray(new byte[0][]);
        }
        long[] cTimes = new long[reps];
        long[] xTimes = new long[reps];
        byte[] packed = null;
        for (int r = 0; r < reps; r++) {
            ByteArrayStream out = new ByteArrayStream((int) total + (16 << 20));
            IOutCreateArchive<IOutItemAllFormats> archive = SevenZip.openOutArchive(format);
            if (archive instanceof IOutFeatureSetLevel) {
                ((IOutFeatureSetLevel) archive).setLevel(level);
            }
            if (archive instanceof IOutFeatureSetMultithreading) {
                ((IOutFeatureSetMultithreading) archive).setThreadCount(threads);
            }
            long t0 = System.nanoTime();
            archive.createArchive(out, items.length, new CreateCallback(items, singleBlob));
            cTimes[r] = System.nanoTime() - t0;
            archive.close();
            packed = out.getBytes();

            CountingExtract cb = new CountingExtract();
            IInArchive in = SevenZip.openInArchive(format, new ByteArrayStream(packed, false));
            t0 = System.nanoTime();
            in.extract(null, false, cb);
            xTimes[r] = System.nanoTime() - t0;
            in.close();
            if (cb.bytes != total || cb.errors != 0) {
                throw new IllegalStateException(name + ": extracted " + cb.bytes + " of " + total + " bytes, "
                        + cb.errors + " errors");
            }
        }
        print(label, name, "compress", cTimes, packed.length);
        print(label, name, "extract", xTimes, packed.length);
    }

    static void print(String label, String name, String op, long[] times, int packed) {
        long[] t = times.clone();
        Arrays.sort(t);
        double minMs = t[0] / 1e6;
        double medMs = (t.length % 2 == 1 ? t[t.length / 2] : (t[t.length / 2 - 1] + t[t.length / 2]) / 2) / 1e6;
        System.out.printf(java.util.Locale.ROOT, "%s,%s,%s,%.1f,%.1f,%.2f,%d%n", label, name, op, minMs, medMs,
                total / 1048576.0 / (minMs / 1000), packed);
    }

    static final class CreateCallback implements IOutCreateCallback<IOutItemAllFormats> {
        final byte[][] items;
        final boolean singleBlob;

        CreateCallback(byte[][] items, boolean singleBlob) {
            this.items = items;
            this.singleBlob = singleBlob;
        }

        public IOutItemAllFormats getItemInformation(int index, OutItemFactory<IOutItemAllFormats> factory) {
            IOutItemAllFormats item = factory.createOutItem();
            item.setDataSize((long) items[index].length);
            if (!singleBlob) {
                item.setPropertyPath(names.get(index));
            }
            return item;
        }

        public ISequentialInStream getStream(int index) {
            return new ByteArrayStream(items[index], false);
        }

        public void setOperationResult(boolean ok) throws SevenZipException {
            if (!ok) {
                throw new SevenZipException("compression failed");
            }
        }

        public void setTotal(long t) {
        }

        public void setCompleted(long c) {
        }
    }

    static final class CountingExtract implements IArchiveExtractCallback {
        long bytes;
        int errors;

        public ISequentialOutStream getStream(int index, ExtractAskMode mode) {
            if (mode != ExtractAskMode.EXTRACT) {
                return null;
            }
            return new ISequentialOutStream() {
                public int write(byte[] d) {
                    bytes += d.length;
                    return d.length;
                }
            };
        }

        public void prepareOperation(ExtractAskMode mode) {
        }

        public void setOperationResult(ExtractOperationResult result) {
            if (result != ExtractOperationResult.OK) {
                errors++;
            }
        }

        public void setTotal(long t) {
        }

        public void setCompleted(long c) {
        }
    }
}
