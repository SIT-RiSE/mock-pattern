package edu.mock.mockpattern.v2;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParseResult;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.Modifier;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.CastExpr;
import com.github.javaparser.ast.expr.EnclosedExpr;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.NameExpr;
import com.github.javaparser.ast.expr.SuperExpr;
import com.github.javaparser.ast.expr.ThisExpr;
import com.github.javaparser.ast.stmt.ReturnStmt;
import com.mockanalyzer.visitor.EnhancedProjectResolver;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Stream;

/**
 * 测试代码的结构索引：测试/setup 方法（按注解识别）、类继承与嵌套、类内调用图、helper 的返回值。
 * 用于判断一条 mock 语句所在的方法是否真正被多个测试共享，而不是按方法名猜。
 * Structural index of test code: test/setup methods (by annotation), class inheritance and
 * nesting, the in-class call graph and helper return values. It decides whether the method
 * holding a mock statement is really shared by several tests instead of guessing by name.
 */
public class TestIndex {

    /** 语句所在位置 / Where a mock statement lives. */
    public enum Location {
        FIELD,            // 字段声明或 @Mock
        SETUP,            // @Before*/@BeforeEach/@BeforeAll/JUnit3 setUp，以及构造器
        TEST,             // 测试方法
        SHARED_HELPER,    // 被 >=2 个测试调用，或被 setup/字段初始化调用的非测试方法
        SINGLE_HELPER,    // 只被 1 个测试调用
        UNREACHED_HELPER, // 没有被任何测试或 setup 调用（例如桩类里的 @Override）
        TEARDOWN,         // @After*/tearDown
        UNKNOWN           // 找不到对应方法
    }

    static final Set<String> TEST_ANNOTATIONS = Set.of("Test", "ParameterizedTest", "RepeatedTest",
            "TestFactory", "TestTemplate", "Theory", "Property", "Example", "CartesianTest", "RetryingTest");
    static final Set<String> SETUP_ANNOTATIONS = Set.of("Before", "BeforeEach", "BeforeClass", "BeforeAll",
            "BeforeMethod", "BeforeTest", "BeforeSuite", "BeforeGroups", "BeforeProperty", "BeforeTry",
            "BeforeContainer");
    static final Set<String> TEARDOWN_ANNOTATIONS = Set.of("After", "AfterEach", "AfterClass", "AfterAll",
            "AfterMethod", "AfterTest", "AfterSuite", "AfterGroups", "AfterProperty", "AfterTry",
            "AfterContainer");

    public static class ClassInfo {
        public String name;
        public String file;
        public String packageName;
        public String superName;
        public ClassInfo enclosing;
        public final List<ClassInfo> nested = new ArrayList<>();
        public final Map<String, List<MethodInfo>> methods = new LinkedHashMap<>();
        /** 字段初始化和构造器里的调用，视作每个测试都会执行的 setup。 */
        public final List<Call> setupCalls = new ArrayList<>();
    }

    public static class MethodInfo {
        public String name;
        public ClassInfo owner;
        public boolean isTest;
        public boolean isSetup;
        public boolean isTeardown;
        public final List<Call> calls = new ArrayList<>();
        /** return 语句返回的变量名 / names returned by return statements. */
        public final Set<String> returnedNames = new HashSet<>();
        /** 是否直接 return mock(...)/spy(...) / whether it returns an inline mock(...) call. */
        public boolean returnsInlineMock;

        public String id() {
            return owner.file + "#" + owner.name + "#" + name;
        }
    }

    /** scope 为 null 表示无限定调用（或 this./super.）；否则为类名限定的静态调用。 */
    public record Call(String scope, String name) {
    }

    private final Map<String, ClassInfo> byFileAndName = new HashMap<>();
    private final Map<String, List<ClassInfo>> bySimpleName = new HashMap<>();
    private final Map<MethodInfo, Set<MethodInfo>> testsReaching = new HashMap<>();
    private final Set<MethodInfo> setupReached = new HashSet<>();
    private int parseFailures;

    public static TestIndex build(Path projectRoot, Collection<String> extraFiles) throws IOException {
        TestIndex index = new TestIndex();
        Set<Path> files = new TreeSet<>();
        try (Stream<Path> paths = Files.walk(projectRoot)) {
            paths.filter(Files::isRegularFile)
                    .filter(p -> p.toString().endsWith(".java"))
                    .filter(p -> isTestPath(projectRoot.relativize(p)))
                    .forEach(files::add);
        }
        for (String f : extraFiles) {
            files.add(Path.of(f));
        }
        JavaParser parser = new JavaParser(EnhancedProjectResolver.parserConfiguration());
        JavaParser legacy = new JavaParser(EnhancedProjectResolver.legacyParserConfiguration());
        for (Path file : files) {
            try {
                ParseResult<CompilationUnit> result = parser.parse(file);
                if (!result.isSuccessful()) {
                    result = legacy.parse(file);
                }
                if (result.isSuccessful() && result.getResult().isPresent()) {
                    index.addCompilationUnit(file.toString(), result.getResult().get());
                } else {
                    index.parseFailures++;
                }
            } catch (Exception | StackOverflowError e) {
                index.parseFailures++;
            }
        }
        index.markJUnit3();
        index.computeReachability();
        return index;
    }

    /** 任一目录名含 "test" 即视为测试源码（src/test、tests、testFixtures、integration-test…）。 */
    static boolean isTestPath(Path relative) {
        for (Path part : relative) {
            if (part.toString().toLowerCase(Locale.ROOT).contains("test")) {
                return true;
            }
        }
        return false;
    }

    public int parseFailures() {
        return parseFailures;
    }

    private void addCompilationUnit(String file, CompilationUnit cu) {
        String pkg = cu.getPackageDeclaration().map(d -> d.getNameAsString()).orElse("");
        for (ClassOrInterfaceDeclaration clazz : cu.findAll(ClassOrInterfaceDeclaration.class)) {
            ClassInfo info = new ClassInfo();
            info.name = clazz.getNameAsString();
            info.file = file;
            info.packageName = pkg;
            info.superName = clazz.getExtendedTypes().isEmpty() ? null
                    : clazz.getExtendedTypes().get(0).getNameAsString();
            byFileAndName.putIfAbsent(key(file, info.name), info);
            bySimpleName.computeIfAbsent(info.name, k -> new ArrayList<>()).add(info);

            for (MethodDeclaration method : clazz.getMethods()) {
                MethodInfo m = new MethodInfo();
                m.name = method.getNameAsString();
                m.owner = info;
                Set<String> annotations = new HashSet<>();
                method.getAnnotations().forEach(a -> annotations.add(a.getName().getIdentifier()));
                m.isTest = annotations.stream().anyMatch(TEST_ANNOTATIONS::contains);
                m.isSetup = !m.isTest && annotations.stream().anyMatch(SETUP_ANNOTATIONS::contains);
                m.isTeardown = !m.isTest && annotations.stream().anyMatch(TEARDOWN_ANNOTATIONS::contains);
                // JUnit3 候选：无测试注解、public void testXxx()；是否继承 TestCase 在 markJUnit3 里确认。
                if (annotations.isEmpty() && method.hasModifier(Modifier.Keyword.PUBLIC)
                        && method.getParameters().isEmpty() && method.getType().isVoidType()) {
                    if (m.name.startsWith("test")) {
                        junit3Candidates.add(m);
                    } else if (m.name.equals("setUp")) {
                        junit3Setup.add(m);
                    } else if (m.name.equals("tearDown")) {
                        junit3Teardown.add(m);
                    }
                } else if (annotations.contains("Override") && method.getParameters().isEmpty()) {
                    if (m.name.equals("setUp")) {
                        junit3Setup.add(m);
                    } else if (m.name.equals("tearDown")) {
                        junit3Teardown.add(m);
                    }
                }
                collectCalls(method, m.calls);
                for (ReturnStmt ret : method.findAll(ReturnStmt.class)) {
                    ret.getExpression().map(TestIndex::unwrap).ifPresent(expr -> {
                        if (expr.isNameExpr()) {
                            m.returnedNames.add(expr.asNameExpr().getNameAsString());
                        } else if (expr.isFieldAccessExpr() && expr.asFieldAccessExpr().getScope().isThisExpr()) {
                            m.returnedNames.add(expr.asFieldAccessExpr().getNameAsString());
                        } else if (expr.isMethodCallExpr()) {
                            String n = expr.asMethodCallExpr().getNameAsString();
                            if (n.equals("mock") || n.equals("spy")) {
                                m.returnsInlineMock = true;
                            }
                        }
                    });
                }
                info.methods.computeIfAbsent(m.name, k -> new ArrayList<>()).add(m);
            }
            for (FieldDeclaration field : clazz.getFields()) {
                collectCalls(field, info.setupCalls);
            }
            for (ConstructorDeclaration ctor : clazz.getConstructors()) {
                collectCalls(ctor, info.setupCalls);
            }
        }
        // 嵌套关系 / nesting
        for (ClassOrInterfaceDeclaration clazz : cu.findAll(ClassOrInterfaceDeclaration.class)) {
            ClassInfo info = byFileAndName.get(key(file, clazz.getNameAsString()));
            Node parent = clazz.getParentNode().orElse(null);
            while (parent != null && !(parent instanceof ClassOrInterfaceDeclaration)) {
                parent = parent.getParentNode().orElse(null);
            }
            if (info != null && parent != null) {
                ClassInfo outer = byFileAndName.get(key(file, ((ClassOrInterfaceDeclaration) parent).getNameAsString()));
                if (outer != null && outer != info) {
                    info.enclosing = outer;
                    outer.nested.add(info);
                }
            }
        }
    }

    private final List<MethodInfo> junit3Candidates = new ArrayList<>();
    private final List<MethodInfo> junit3Setup = new ArrayList<>();
    private final List<MethodInfo> junit3Teardown = new ArrayList<>();

    private void markJUnit3() {
        for (MethodInfo m : junit3Candidates) {
            if (extendsTestCase(m.owner)) {
                m.isTest = true;
            }
        }
        for (MethodInfo m : junit3Setup) {
            if (extendsTestCase(m.owner)) {
                m.isSetup = true;
            }
        }
        for (MethodInfo m : junit3Teardown) {
            if (extendsTestCase(m.owner)) {
                m.isTeardown = true;
            }
        }
    }

    private boolean extendsTestCase(ClassInfo clazz) {
        Set<ClassInfo> seen = new HashSet<>();
        ClassInfo current = clazz;
        while (current != null && seen.add(current)) {
            if (current.superName == null) {
                return false;
            }
            if (current.superName.equals("TestCase") || current.superName.endsWith("TestCase")) {
                return true;
            }
            current = findClass(current.superName, current.file);
        }
        return false;
    }

    private static Expression unwrap(Expression expr) {
        while (expr instanceof EnclosedExpr || expr instanceof CastExpr) {
            expr = expr instanceof EnclosedExpr ? ((EnclosedExpr) expr).getInner()
                    : ((CastExpr) expr).getExpression();
        }
        return expr;
    }

    private static void collectCalls(Node node, List<Call> out) {
        for (MethodCallExpr call : node.findAll(MethodCallExpr.class)) {
            Optional<Expression> scope = call.getScope();
            if (scope.isEmpty() || scope.get() instanceof ThisExpr || scope.get() instanceof SuperExpr) {
                out.add(new Call(null, call.getNameAsString()));
            } else if (scope.get() instanceof NameExpr) {
                String s = ((NameExpr) scope.get()).getNameAsString();
                if (!s.isEmpty() && Character.isUpperCase(s.charAt(0))) {
                    out.add(new Call(s, call.getNameAsString()));
                }
            }
        }
    }

    private static String key(String file, String className) {
        return file + "#" + className;
    }

    public ClassInfo getClass(String file, String className) {
        return byFileAndName.get(key(file, className));
    }

    /** 按简单类名查找，优先同文件，其次任意一个 / by simple name, same file first. */
    public ClassInfo findClass(String simpleName, String fromFile) {
        List<ClassInfo> candidates = bySimpleName.get(simpleName);
        if (candidates == null || candidates.isEmpty()) {
            return null;
        }
        for (ClassInfo c : candidates) {
            if (c.file.equals(fromFile)) {
                return c;
            }
        }
        return candidates.get(0);
    }

    /**
     * 在类本身、外部类、父类链中查找方法（按名字，重载合并）。
     * Looks the method up in the class, its enclosing classes and its superclass chain.
     */
    public List<MethodInfo> resolveUnqualified(ClassInfo from, String methodName) {
        Set<ClassInfo> seen = new HashSet<>();
        for (ClassInfo scope = from; scope != null; scope = scope.enclosing) {
            ClassInfo current = scope;
            while (current != null && seen.add(current)) {
                List<MethodInfo> found = current.methods.get(methodName);
                if (found != null) {
                    return found;
                }
                current = current.superName == null ? null : findClass(current.superName, current.file);
            }
        }
        return List.of();
    }

    public List<MethodInfo> resolve(ClassInfo from, Call call) {
        if (call.scope() == null) {
            return resolveUnqualified(from, call.name());
        }
        ClassInfo target = findClass(call.scope(), from.file);
        return target == null ? List.of() : resolveUnqualified(target, call.name());
    }

    /**
     * 语句所在方法的查找：mock 所在类 → 其嵌套类 → 外部类/父类链。
     * Finds the method holding a statement: the mock's class, its nested classes, then outward.
     */
    public List<MethodInfo> findMethod(String file, String className, String methodName) {
        ClassInfo clazz = getClass(file, className);
        if (clazz == null) {
            return List.of();
        }
        Deque<ClassInfo> queue = new ArrayDeque<>(List.of(clazz));
        while (!queue.isEmpty()) {
            ClassInfo c = queue.poll();
            List<MethodInfo> found = c.methods.get(methodName);
            if (found != null) {
                return found;
            }
            queue.addAll(c.nested);
        }
        return resolveUnqualified(clazz, methodName);
    }

    private void computeReachability() {
        for (List<ClassInfo> classes : bySimpleName.values()) {
            for (ClassInfo clazz : classes) {
                for (List<MethodInfo> overloads : clazz.methods.values()) {
                    for (MethodInfo m : overloads) {
                        if (m.isTest) {
                            walk(m, m, new HashSet<>(), false);
                        } else if (m.isSetup) {
                            walk(m, m, new HashSet<>(), true);
                        }
                    }
                }
                Set<MethodInfo> visited = new HashSet<>();
                for (Call call : clazz.setupCalls) {
                    for (MethodInfo target : resolve(clazz, call)) {
                        markSetup(target, clazz, visited);
                    }
                }
            }
        }
    }

    private void walk(MethodInfo root, MethodInfo current, Set<MethodInfo> visited, boolean fromSetup) {
        for (Call call : current.calls) {
            List<MethodInfo> targets = resolve(current.owner, call);
            if (targets.isEmpty() && current.owner != root.owner) {
                // 虚调用：父类 helper 调用的方法可能定义在子类里 / virtual dispatch into the test's class
                targets = resolve(root.owner, call);
            }
            for (MethodInfo target : targets) {
                if (target.isTest || target == root || !visited.add(target)) {
                    continue;
                }
                if (fromSetup) {
                    setupReached.add(target);
                } else {
                    testsReaching.computeIfAbsent(target, k -> new HashSet<>()).add(root);
                }
                walk(root, target, visited, fromSetup);
            }
        }
    }

    private void markSetup(MethodInfo target, ClassInfo from, Set<MethodInfo> visited) {
        if (target.isTest || !visited.add(target)) {
            return;
        }
        setupReached.add(target);
        for (Call call : target.calls) {
            for (MethodInfo next : resolve(target.owner, call)) {
                markSetup(next, from, visited);
            }
        }
    }

    /** 语句所在方法的位置分类 / Location of the method(s) that hold a statement. */
    public Location locate(List<MethodInfo> methods) {
        if (methods.isEmpty()) {
            return Location.UNKNOWN;
        }
        boolean anyTest = false, anySetup = false, anyTeardown = false, reachedBySetup = false;
        Set<MethodInfo> tests = new HashSet<>();
        for (MethodInfo m : methods) {
            anyTest |= m.isTest;
            anySetup |= m.isSetup;
            anyTeardown |= m.isTeardown;
            reachedBySetup |= setupReached.contains(m);
            tests.addAll(testsReaching.getOrDefault(m, Set.of()));
        }
        if (anyTest) {
            return Location.TEST;
        }
        if (anySetup) {
            return Location.SETUP;
        }
        if (anyTeardown) {
            return Location.TEARDOWN;
        }
        if (reachedBySetup || tests.size() >= 2) {
            return Location.SHARED_HELPER;
        }
        return tests.size() == 1 ? Location.SINGLE_HELPER : Location.UNREACHED_HELPER;
    }

    public int testsReachingCount(List<MethodInfo> methods) {
        Set<MethodInfo> tests = new HashSet<>();
        for (MethodInfo m : methods) {
            tests.addAll(testsReaching.getOrDefault(m, Set.of()));
        }
        return tests.size();
    }
}
