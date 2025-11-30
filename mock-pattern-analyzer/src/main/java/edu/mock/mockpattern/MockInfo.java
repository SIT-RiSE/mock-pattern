package edu.mock.mockpattern;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * Represents a mock object detected in the source code.
 * Simplified version for AST-only analysis (no project dependency).
 */
public class MockInfo {

    /** Unique numeric ID for each detected mock object */
    public int rawMockObjectId;

    /** The variable name of the mock (e.g., userServiceMock) */
    public String variableName;

    /** The declared or inferred type of the mock (e.g., UserService) */
    public String variableType;

    boolean isGlobal = false; // 是否为全局mock对象

    /** Pattern level of this mock (optional: 1–4, following the maturity model) */
    public int mockPatternLevel;

    // 类上下文
    // ClassContext
    public ClassContext classContext = new ClassContext();

    // locationContext
    public List<StatementInfo> statements = new ArrayList<>();

    public List<String> stubbedInfo = new ArrayList<>();

    public static class ClassContext {
        public String packageName;
        public String filePath;
        public String className;
        // Getter & Setter
    }

    public boolean isEqual(MockInfo other) {
        if (other == null)
            return false;
        if (this == other)
            return true;

        boolean basicEqual = Objects.equals(this.variableName, other.variableName)
                && Objects.equals(this.variableType, other.variableType)
                && Objects.equals(this.classContext.packageName, other.classContext.packageName)
                && Objects.equals(this.classContext.filePath, other.classContext.filePath)
                && Objects.equals(this.classContext.className, other.classContext.className);

        if (!basicEqual)
            return false;

        if (this.statements.size() != other.statements.size())
            return false;
        for (int i = 0; i < this.statements.size(); i++) {
            StatementInfo s1 = this.statements.get(i);
            StatementInfo s2 = other.statements.get(i);
            if (s1 == null && s2 == null)
                continue;
            if (s1 == null || s2 == null)
                return false;
            if (!s1.isEqual(s2))
                return false;
        }
        return true;
    }

    public void checkMockPatternLevel() {
        if (!isGlobal) {
            this.mockPatternLevel = 0;
            return;
        }

        boolean hasStaticSharedStubbing = false;
        boolean hasTestStubbing = false;
        boolean hasHelperTestStubbing = false;

        for (StatementInfo stmt : statements) {
            stmt.checkLocate();
            if ("CREATION".equals(stmt.type) && stmt.isShareable) {
                hasStaticSharedStubbing = true;
            } else if ("STUBBING".equals(stmt.type) && "@Before".equals(stmt.locate)) {
                hasStaticSharedStubbing = true;
            } else if ("STUBBING".equals(stmt.type) && "Test Case".equals(stmt.locate)) {
                hasTestStubbing = true;
            } else if ("STUBBING".equals(stmt.type) && "Helper Method".equals(stmt.locate)) {
                hasHelperTestStubbing = true;
            }
        }

        if (hasStaticSharedStubbing && !hasTestStubbing && !hasHelperTestStubbing) {
            this.mockPatternLevel = 1;
        } else if (hasHelperTestStubbing && !hasTestStubbing) {
            this.mockPatternLevel = 1;
        } else if ((hasStaticSharedStubbing || hasHelperTestStubbing) && hasTestStubbing) {
            this.mockPatternLevel = 2;
        }

    }
    public void generateStubbedInfo() {
        stubbedInfo.clear(); // 防止重复调用时残留

        for (StatementInfo stmt : this.statements) {
            if (stmt == null) continue;

            String method = stmt.stubbedMethod;
            if (method != null && !method.isEmpty()) {
                stubbedInfo.add(method);
            }
        }
    }

    public MockInfo copy() {
        MockInfo clone = new MockInfo();

        // 基本字段复制
        clone.rawMockObjectId = this.rawMockObjectId;
        clone.variableName = this.variableName;
        clone.variableType = this.variableType;
        clone.isGlobal = this.isGlobal;
        clone.mockPatternLevel = this.mockPatternLevel;

        // 拷贝 classContext
        clone.classContext = new ClassContext();
        if (this.classContext != null) {
            clone.classContext.packageName = this.classContext.packageName;
            clone.classContext.filePath = this.classContext.filePath;
            clone.classContext.className = this.classContext.className;
        }

        // 深拷贝 statements
        clone.statements = new ArrayList<>();
        for (StatementInfo stmt : this.statements) {
            if (stmt != null) {
                clone.statements.add(stmt.copy());
            }
        }
        clone.stubbedInfo = new ArrayList<>(this.stubbedInfo);

        return clone;
    }

}
