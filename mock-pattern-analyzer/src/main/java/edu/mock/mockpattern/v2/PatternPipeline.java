package edu.mock.mockpattern.v2;

import com.github.javaparser.StaticJavaParser;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.mockanalyzer.cloneDetector.MockCloneDetector;
import com.mockanalyzer.exporter.MockInfoExporter;
import com.mockanalyzer.model.DetectionScope;
import com.mockanalyzer.model.MockCloneInstance;
import com.mockanalyzer.model.MockInfo;
import com.mockanalyzer.model.MockSequence;
import com.mockanalyzer.model.StatementInfo;
import com.mockanalyzer.visitor.EnhancedProjectResolver;
import edu.mock.mockpattern.v2.LevelClassifier.MockRecord;

import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * mock-pattern v2：用 CloneDeMocker-v2 的检测提取 mock 和 MCI，再做 L0/L1/L2 分级与升级统计。不编译被测项目。
 * mock-pattern v2: extracts mocks and MCIs with CloneDeMocker-v2's detection, then derives L0/L1/L2
 * and the upgrade statistics. The subject project is never compiled.
 *
 * <pre>java -jar mock-analyzer-1.0-jar-with-dependencies.jar &lt;projectRoot&gt; &lt;outDir&gt; [--resolve]</pre>
 *
 * 输出 / outputs: mock-objects.json, excluded.json, mci.json, summary.json
 */
public class PatternPipeline {

    public static class Summary {
        public String projectRoot;
        public int scannedMockInfos;
        public int mocks;
        public int excludedSpy;
        public int excludedNoCreation;
        public int helperReturnedMerged;
        public int l0, l1, l2;
        public int l0WithoutStub;
        public int stubStatements;
        public int mciCount;
        public int mciMocks;
        public int mciL0Mocks;
        public int mciL1Mocks;
        public int mciL2Mocks;
        public int mocksReduced;
        /** 抽象口径（CloneDeMocker 的 stub 抽象）/ abstracted measure. */
        public int stubsReduced;
        /** 精确口径（代码相同才合并）/ exact measure. */
        public int stubsReducedExact;
        public int indexParseFailures;
        public double scanSeconds;
        public double totalSeconds;
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("Usage: <projectRoot> <outDir> [--resolve]");
            System.exit(1);
        }
        Path root = Path.of(args[0]);
        Path out = Path.of(args[1]);
        boolean resolve = Arrays.asList(args).contains("--resolve");
        Files.createDirectories(out);
        Summary summary = run(root, out, resolve);
        System.out.printf("[DONE] mocks=%d L0=%d L1=%d L2=%d MCIs=%d mocksReduced=%d stubsReduced=%d exact=%d (%.1fs)%n",
                summary.mocks, summary.l0, summary.l1, summary.l2, summary.mciCount, summary.mocksReduced,
                summary.stubsReduced, summary.stubsReducedExact, summary.totalSeconds);
    }

    public static Summary run(Path root, Path out, boolean resolveDependencies) throws Exception {
        long start = System.nanoTime();
        StaticJavaParser.setConfiguration(EnhancedProjectResolver.parserConfiguration());
        Summary s = new Summary();
        s.projectRoot = root.toString();

        // 1. CloneDeMocker-v2 mock 提取 / mock extraction
        List<MockInfo> mocks = MockInfoExporter.analyzeProject(root, resolveDependencies, DetectionScope.all());
        s.scanSeconds = (System.nanoTime() - start) / 1e9;
        s.scannedMockInfos = mocks.size();

        // 2. CloneDeMocker-v2 MCI 检测，筛选规则与 MockCloneExporter 相同；先于分级执行，保证输入未被改动。
        //    MCI detection with MockCloneExporter's filter, run before leveling so its input is untouched.
        List<MockSequence> sequences = new ArrayList<>();
        for (MockInfo m : mocks) {
            if (!m.isSpy() && !m.isGlobalFinal()) {
                sequences.addAll(m.toMockSequences());
            }
        }
        Map<String, List<MockCloneInstance>> mcis = sequences.isEmpty() ? new LinkedHashMap<>()
                : new MockCloneDetector().detect(sequences);

        // 3. 分级 / leveling
        Set<String> mockFiles = new HashSet<>();
        mocks.forEach(m -> mockFiles.add(m.classContext.filePath));
        TestIndex index = TestIndex.build(root, mockFiles);
        s.indexParseFailures = index.parseFailures();
        LevelClassifier classifier = new LevelClassifier(index);
        classifier.classify(mocks);
        Map<Integer, MockRecord> byId = new HashMap<>();
        for (MockRecord r : classifier.records()) {
            byId.put(r.id, r);
        }

        // 4. 升级统计 / upgrade statistics
        Set<Integer> mciIds = new HashSet<>();
        for (List<MockCloneInstance> list : mcis.values()) {
            for (MockCloneInstance mci : list) {
                s.mciCount++;
                s.mocksReduced += mci.mockObjectCount - 1;
                int matchedStubs = 0;
                // 抽象形式相同但取值不同的 stub（如 thenReturn(false) 与 thenReturn(true)）无法放进同一个 helper：
                // 精确口径按“mock 变量名替换后代码完全相同”分组，每个核心 stub 只取出现最多的写法。
                // Stubs equal only in abstracted form (thenReturn(false) vs thenReturn(true)) cannot share one
                // helper: the exact measure groups by code identical after renaming the mock variable and keeps,
                // per core stub, only the most frequent variant.
                Map<String, Map<String, Integer>> variants = new HashMap<>();
                for (MockSequence seq : mci.sequences) {
                    mciIds.add(seq.mockObjectId);
                    for (int line : seq.overlapLines) {
                        StatementInfo st = seq.rawStatementInfo.get(line);
                        if (st != null && "STUBBING".equals(st.type) && !st.isShareable) {
                            matchedStubs++;
                            variants.computeIfAbsent(st.abstractedStatement, k -> new HashMap<>())
                                    .merge(normalize(st.code, seq.variableName), 1, Integer::sum);
                        }
                    }
                }
                int core = mci.sharedStatements == null ? 0 : mci.sharedStatements.size();
                if (core > 0) {
                    s.stubsReduced += Math.max(0, matchedStubs - core);
                    for (Map<String, Integer> byCode : variants.values()) {
                        int best = Collections.max(byCode.values());
                        s.stubsReducedExact += Math.max(0, best - 1);
                    }
                }
            }
        }
        for (int id : mciIds) {
            MockRecord r = byId.get(id);
            if (r == null) {
                continue;
            }
            r.inMci = true;
            s.mciMocks++;
            switch (r.level) {
                case 0 -> s.mciL0Mocks++;
                case 1 -> s.mciL1Mocks++;
                default -> s.mciL2Mocks++;
            }
        }

        for (MockRecord r : classifier.records()) {
            s.mocks++;
            s.stubStatements += r.stubCount;
            switch (r.level) {
                case 0 -> {
                    s.l0++;
                    if (r.stubCount == 0) {
                        s.l0WithoutStub++;
                    }
                }
                case 1 -> s.l1++;
                default -> s.l2++;
            }
            if (r.mergedCallSites > 0) {
                s.helperReturnedMerged += r.mergedCallSites;
            }
        }
        for (LevelClassifier.Excluded e : classifier.excluded()) {
            if ("spy".equals(e.reason)) {
                s.excludedSpy++;
            } else {
                s.excludedNoCreation++;
            }
        }
        s.totalSeconds = (System.nanoTime() - start) / 1e9;

        write(out.resolve("mock-objects.json"), classifier.records());
        write(out.resolve("excluded.json"), classifier.excluded());
        write(out.resolve("mci.json"), mcis);
        write(out.resolve("summary.json"), s);
        return s;
    }

    /** 去掉空白并把 mock 变量名替换为占位符 / strips whitespace and renames the mock variable. */
    static String normalize(String code, String variableName) {
        String c = code.replaceAll("\\s+", "");
        if (variableName != null && !variableName.isEmpty() && !variableName.startsWith("$")) {
            c = c.replaceAll("\\b" + java.util.regex.Pattern.quote(variableName) + "\\b", "\\$m");
        }
        return c;
    }

    private static void write(Path path, Object value) throws IOException {
        Gson gson = new GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create();
        try (Writer w = Files.newBufferedWriter(path, StandardCharsets.UTF_8)) {
            gson.toJson(value, w);
        }
    }
}
