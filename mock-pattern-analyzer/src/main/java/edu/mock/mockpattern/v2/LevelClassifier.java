package edu.mock.mockpattern.v2;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.expr.CastExpr;
import com.github.javaparser.ast.expr.EnclosedExpr;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.NameExpr;
import com.github.javaparser.ast.expr.ThisExpr;
import com.github.javaparser.ast.expr.VariableDeclarationExpr;
import com.github.javaparser.ast.stmt.ExpressionStmt;
import com.github.javaparser.ast.stmt.Statement;
import com.mockanalyzer.model.MockInfo;
import com.mockanalyzer.model.StatementInfo;
import edu.mock.mockpattern.v2.TestIndex.Location;
import edu.mock.mockpattern.v2.TestIndex.MethodInfo;

import java.util.*;

/**
 * 在 CloneDeMocker-v2 提取的 mock 上重新判定 L0/L1/L2。
 * Re-derives L0/L1/L2 on the mocks extracted by CloneDeMocker-v2.
 *
 * <ul>
 *   <li>C（创建）共享：创建语句位于字段、setup，或被 >=2 个测试 / setup 调用的 helper。</li>
 *   <li>S（stub）共享：stub 位于 setup 或共享 helper；其余（测试方法、只被一个测试调用的 helper）为本地。</li>
 *   <li>L0: C 本地且无共享 stub；L1: C 共享且无本地 stub；L2: C 共享且有本地 stub
 *       （与旧实现一致：共享创建 + 本地扩展即为部分共享）。</li>
 *   <li>spy 与找不到创建语句的变量被排除；helper 返回的 mock 在调用处的 stub 合并回该 mock。</li>
 * </ul>
 */
public class LevelClassifier {

    static final Set<String> MOCK_CREATION = Set.of("FIELD_MOCK_CREATION", "METHOD_MOCK_CREATION", "ASSIGNMENT_MOCK");
    static final Set<String> SPY_CREATION = Set.of("FIELD_SPY_CREATION", "METHOD_SPY_CREATION", "ASSIGNMENT_SPY");
    static final EnumSet<Location> SHARED_CREATION = EnumSet.of(Location.FIELD, Location.SETUP, Location.SHARED_HELPER);
    static final EnumSet<Location> SHARED_STUB = EnumSet.of(Location.SETUP, Location.SHARED_HELPER);

    /** 输出记录 / one output row per mock object. */
    public static class MockRecord {
        public int id;
        public String variableName;
        public String mockedClass;
        public String packageName;
        public String filePath;
        public String className;
        public int level;
        public String creationLocation;
        public int stubCount;
        public int sharedStubCount;
        public int testCount;
        public int mergedCallSites;
        public boolean globalFinal;
        public boolean inMci;
        public List<String> flags = new ArrayList<>();
    }

    public static class Excluded {
        public int id;
        public String variableName;
        public String filePath;
        public String className;
        public String reason;
    }

    private final TestIndex index;
    private final List<MockRecord> records = new ArrayList<>();
    private final List<Excluded> excluded = new ArrayList<>();

    public LevelClassifier(TestIndex index) {
        this.index = index;
    }

    public List<MockRecord> records() {
        return records;
    }

    public List<Excluded> excluded() {
        return excluded;
    }

    public void classify(List<MockInfo> mocks) {
        Map<Integer, List<StatementInfo>> extensions = new HashMap<>();
        Map<Integer, Integer> mergedCount = new HashMap<>();
        List<MockInfo> real = new ArrayList<>();

        for (MockInfo mock : mocks) {
            boolean hasMock = mock.statements.stream().anyMatch(s -> MOCK_CREATION.contains(s.type));
            boolean hasSpy = mock.statements.stream().anyMatch(s -> SPY_CREATION.contains(s.type));
            if (hasMock) {
                real.add(mock);
            } else if (hasSpy) {
                exclude(mock, "spy");
            }
        }
        for (MockInfo mock : mocks) {
            boolean hasCreation = mock.statements.stream()
                    .anyMatch(s -> MOCK_CREATION.contains(s.type) || SPY_CREATION.contains(s.type));
            if (hasCreation) {
                continue;
            }
            MockInfo origin = findHelperOrigin(mock, real);
            if (origin == null) {
                exclude(mock, "no-creation");
                continue;
            }
            List<StatementInfo> ext = extensions.computeIfAbsent(origin.rawMockObjectId, k -> new ArrayList<>());
            for (StatementInfo s : mock.statements) {
                if ("STUBBING".equals(s.type)) {
                    ext.add(s);
                }
            }
            mergedCount.merge(origin.rawMockObjectId, 1, Integer::sum);
        }
        for (MockInfo mock : real) {
            records.add(level(mock, extensions.getOrDefault(mock.rawMockObjectId, List.of()),
                    mergedCount.getOrDefault(mock.rawMockObjectId, 0)));
        }
    }

    private void exclude(MockInfo mock, String reason) {
        Excluded e = new Excluded();
        e.id = mock.rawMockObjectId;
        e.variableName = mock.variableName;
        e.filePath = mock.classContext.filePath;
        e.className = mock.classContext.className;
        e.reason = reason;
        excluded.add(e);
    }

    private MockRecord level(MockInfo mock, List<StatementInfo> extensionStubs, int merged) {
        MockRecord r = new MockRecord();
        r.id = mock.rawMockObjectId;
        r.variableName = mock.variableName;
        r.mockedClass = mock.mockedClass;
        r.packageName = mock.classContext.packageName;
        r.filePath = mock.classContext.filePath;
        r.className = mock.classContext.className;
        r.globalFinal = mock.isGlobalFinal();
        r.mergedCallSites = merged;

        boolean creationShared = false;
        Location firstCreation = null;
        Set<String> tests = new HashSet<>();
        Set<String> seenStubs = new HashSet<>();
        int sharedStubs = 0, localStubs = 0;

        List<StatementInfo> all = new ArrayList<>(mock.statements);
        all.addAll(extensionStubs);
        for (StatementInfo s : all) {
            boolean creation = MOCK_CREATION.contains(s.type);
            boolean stub = "STUBBING".equals(s.type);
            if (!creation && !stub && !"VERIFICATION".equals(s.type) && !"REFERENCE".equals(s.type)) {
                continue;
            }
            Location loc = locate(mock, s);
            if (loc == Location.TEST) {
                tests.add(s.locationContext.methodName);
            }
            if (creation) {
                if (firstCreation == null) {
                    firstCreation = loc;
                }
                creationShared |= SHARED_CREATION.contains(loc);
            }
            if (stub && seenStubs.add(s.line + "|" + s.code)) {
                if (SHARED_STUB.contains(loc)) {
                    sharedStubs++;
                } else {
                    localStubs++;
                }
            }
        }
        r.creationLocation = firstCreation == null ? "NONE" : firstCreation.name();
        r.stubCount = sharedStubs + localStubs;
        r.sharedStubCount = sharedStubs;
        r.testCount = tests.size();
        if (!creationShared) {
            r.level = sharedStubs > 0 ? 2 : 0;
            if (sharedStubs > 0) {
                r.flags.add("local-creation-shared-stub");
            }
        } else {
            r.level = localStubs > 0 ? 2 : 1;
        }
        if (firstCreation == Location.UNREACHED_HELPER) {
            r.flags.add("unreached-by-tests");
        }
        if (merged > 0) {
            r.flags.add("helper-returned");
        }
        return r;
    }

    private Location locate(MockInfo mock, StatementInfo s) {
        String method = s.locationContext.methodName;
        if ("FieldDeclaration".equals(method)) {
            return Location.FIELD;
        }
        List<MethodInfo> methods = index.findMethod(mock.classContext.filePath, mock.classContext.className, method);
        return index.locate(methods);
    }

    /**
     * 对没有创建语句的局部变量，若其初始化为调用某个 helper，且该 helper return 了一个 mock，
     * 返回那个 mock。 / For a local variable without creation whose initializer calls a helper
     * returning a mock, returns that mock.
     */
    private MockInfo findHelperOrigin(MockInfo var, List<MockInfo> real) {
        for (StatementInfo s : var.statements) {
            if (!"METHOD_VARIABLE_INITIALIZATION".equals(s.type) && !"ASSIGNMENT".equals(s.type)) {
                continue;
            }
            MethodCallExpr call = initializerCall(s.code);
            if (call == null) {
                continue;
            }
            TestIndex.ClassInfo from = index.getClass(var.classContext.filePath, var.classContext.className);
            if (from == null) {
                continue;
            }
            String scope = null;
            if (call.getScope().isPresent()) {
                Expression sc = call.getScope().get();
                if (sc instanceof NameExpr && Character.isUpperCase(((NameExpr) sc).getNameAsString().charAt(0))) {
                    scope = ((NameExpr) sc).getNameAsString();
                } else if (!(sc instanceof ThisExpr)) {
                    continue;
                }
            }
            for (MethodInfo helper : index.resolve(from, new TestIndex.Call(scope, call.getNameAsString()))) {
                if (helper.isTest) {
                    continue;
                }
                for (MockInfo candidate : real) {
                    if (!candidate.classContext.filePath.equals(helper.owner.file)) {
                        continue;
                    }
                    boolean createdInHelper = candidate.statements.stream().anyMatch(st -> MOCK_CREATION.contains(st.type)
                            && helper.name.equals(st.locationContext.methodName));
                    boolean returnedByName = helper.returnedNames.contains(candidate.variableName)
                            && (createdInHelper || candidate.statements.stream()
                                    .anyMatch(st -> "FieldDeclaration".equals(st.locationContext.methodName)));
                    boolean returnedInline = helper.returnsInlineMock && candidate.variableName.startsWith("$inline")
                            && createdInHelper;
                    if (returnedByName || returnedInline) {
                        return candidate;
                    }
                }
            }
        }
        return null;
    }

    private static MethodCallExpr initializerCall(String code) {
        try {
            Statement stmt = StaticJavaParser.parseStatement(code.trim().endsWith(";") ? code : code + ";");
            if (!(stmt instanceof ExpressionStmt)) {
                return null;
            }
            Expression expr = ((ExpressionStmt) stmt).getExpression();
            Expression value;
            if (expr instanceof VariableDeclarationExpr v && !v.getVariables().isEmpty()
                    && v.getVariable(0).getInitializer().isPresent()) {
                value = v.getVariable(0).getInitializer().get();
            } else if (expr.isAssignExpr()) {
                value = expr.asAssignExpr().getValue();
            } else {
                return null;
            }
            while (value instanceof EnclosedExpr || value instanceof CastExpr) {
                value = value instanceof EnclosedExpr ? ((EnclosedExpr) value).getInner()
                        : ((CastExpr) value).getExpression();
            }
            return value instanceof MethodCallExpr ? (MethodCallExpr) value : null;
        } catch (Exception e) {
            return null;
        }
    }
}
