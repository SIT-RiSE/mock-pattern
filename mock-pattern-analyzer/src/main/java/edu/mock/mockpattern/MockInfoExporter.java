package edu.mock.mockpattern;

import com.github.javaparser.ParseResult;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.ImportDeclaration;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;
import com.github.javaparser.JavaParser;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;

public class MockInfoExporter {

    public static void main(String[] args) throws Exception {
        // String mode = "clone"; // pattern / clone
        // String projectRoot = "C:\\Java_projects\\temp_projects\\NiFi"; // ← 你可以直接改这里
        // String outputPath = "C:\\Users\\10590\\OneDrive - stevens.edu\\PHD\\2025 Fall\\mock pattern\\mock-pattern-analyzer\\NiFi.json";
        // 参数检查
    // Usage 检查
        if (args.length < 3) {
            System.out.println("""
            Usage: java -jar mock-analyzer-lite.jar <mode> <source_dir> <output_json>

            <mode>         'pattern' or 'clone'
            <source_dir>   Path to the root directory of Java source files to analyze
            <output_json>  Path to the output JSON file

            Examples:
              java -jar mock-analyzer-lite.jar pattern ./src/test/java ./output/mock_info.json
              java -jar mock-analyzer-lite.jar clone ./src/test/java ./output/mock_clone_instances.json
            """);
            return;
        }

        String mode = args[0].toLowerCase(); // pattern / clone
        String projectRoot = args[1];
        String outputPath = args[2];

        Path projectRootPath = Path.of(projectRoot);
        if (!Files.exists(projectRootPath) || !Files.isDirectory(projectRootPath)) {
            System.err.println("Error: Invalid project root -> " + projectRoot);
            System.exit(1);
        }

        try {
            switch (mode) {
                case "pattern" -> {
                    System.out.println("[INFO] Running in PATTERN mode...");
                    List<MockInfo> combinedResults = analyzeProject(projectRootPath);
                    writeMockInfoToJson(combinedResults, outputPath);
                    System.out.println("Pattern analysis completed. Result -> " + outputPath);
                }
                case "clone" -> {
                    System.out.println("[INFO] Running in CLONE mode...");
                    
                    List<MockInfo> combinedResults = analyzeProject(projectRootPath);
                    MockCloneInstanceGenerator mockCloneGenerator = new MockCloneInstanceGenerator(combinedResults);
                    // 调用另一套逻辑，例如 MockCloneInstanceGenerator
                    List<CloneInstance> cloneInstance = mockCloneGenerator.generateCloneInstances();
                    
                    writeMockInfoToJson(cloneInstance, outputPath);
                    System.out.println("Clone instance generation completed. Result -> " + outputPath);
                }
                default -> {
                    System.err.println("Error: Unknown mode '" + mode + "'. Must be 'pattern' or 'clone'.");
                    System.exit(1);
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static List<MockInfo> analyzeProject(Path projectRoot)
            throws IOException, InterruptedException {
        List<MockInfo> combinedResults = new ArrayList<>();
        JavaParser parser = new JavaParser();

        // 收集所有 Java 文件
        List<Path> javaFiles = new ArrayList<>();
        try (Stream<Path> paths = Files.walk(projectRoot)) {
            paths.filter(p -> p.toString().endsWith(".java")).forEach(javaFiles::add);
        }

        int mockCount = 1;
        for (Path javaFile : javaFiles) {
            try {
                ParseResult<CompilationUnit> parseResult = parser.parse(javaFile);
                if (parseResult.isSuccessful() && parseResult.getResult().isPresent()) {
                    CompilationUnit cu = parseResult.getResult().get();

                    // 判断是否包含 Mockito 导入
                    boolean hasMockitoImport = cu.findAll(ImportDeclaration.class).stream()
                            .anyMatch(imp -> imp.getNameAsString().startsWith("org.mockito"));

                    if (hasMockitoImport) {
                        MockCollectorVisitor visitor = new MockCollectorVisitor(javaFile.toString());
                        visitor.visit(cu, null);

                        List<MockInfo> mockList = visitor.getFinalMockList();
                        for (MockInfo info : mockList) {
                            info.rawMockObjectId = mockCount++;
                            info.classContext.filePath = javaFile.toString();
                            info.generateStubbedInfo();
                        }
                        combinedResults.addAll(mockList);
                    }
                } else {
                    System.err.println("[WARN] Parse failed: " + javaFile);
                }
            } catch (Exception e) {
                System.err.println("[WARN] Skipping file due to exception: " + javaFile + " - " + e.getMessage());
            }
        }

        return combinedResults;
    }

    /** 导出 JSON */
    public static void writeMockInfoToJson(Object mockInfos, String outputPath) {
        Gson gson = new GsonBuilder()
                .setPrettyPrinting()
                .disableHtmlEscaping()
                .create();

        try (OutputStreamWriter writer = new OutputStreamWriter(
                new FileOutputStream(outputPath), StandardCharsets.UTF_8)) {
            gson.toJson(mockInfos, writer);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}