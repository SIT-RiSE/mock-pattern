package edu.mock.mockpattern;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class CloneInstance {

    /** Unique ID of this clone instance */
    public int instanceId;

    /** The mocked class type (e.g., "UserService") */
    public String variableType;

    /** Number of mock objects participating in this clone instance */
    public int convertedLevel;

    public int numberOfConverted = 0;

    /** Core stubbed methods shared across this clone instance */
    public List<String> coreStubbedMethods = new ArrayList<>();
    

    public String sharedLogic = "";

    /** All mock objects that form this clone instance */
    public List<MockInfo> involvedMocks = new ArrayList<>();

    public CloneInstance(int instanceId,
            String variableType,
            int convertedLevel,
            List<String> coreStubbedMethods,
            List<MockInfo> involvedMocks) {

        this.instanceId = instanceId;
        this.variableType = variableType;
        this.convertedLevel = convertedLevel;

        if (coreStubbedMethods != null) {
            this.coreStubbedMethods = new ArrayList<>(coreStubbedMethods);
        } else {
            this.coreStubbedMethods = new ArrayList<>();
        }

        if (involvedMocks != null) {
            this.numberOfConverted = involvedMocks.size();
            this.involvedMocks = new ArrayList<>();
            for (MockInfo mock : involvedMocks) {
                this.involvedMocks.add(mock.copy());
            }
        } else {
            this.involvedMocks = new ArrayList<>();
        }

        // 自动计算 convertedLevel
        computeConvertedLevel();
        generateSharedLogic();
    }

    public void computeConvertedLevel() {
        Set<String> coreSet = new HashSet<>(coreStubbedMethods);
        for (MockInfo mock : involvedMocks) {
            Set<String> mockSet = new HashSet<>(mock.stubbedInfo);
            if (!mockSet.equals(coreSet)) {
                this.convertedLevel = 2;
                return;
            }
        }
        this.convertedLevel = 1;
    }

    public void generateSharedLogic() {
        StringBuilder builder = new StringBuilder();

        // 1️⃣ 如果 coreStubbedMethods 为空 → 简单 @Mock 声明
        if (coreStubbedMethods == null || coreStubbedMethods.isEmpty()) {
            builder.append("@Mock\n")
                    .append(variableType)
                    .append(" mock")
                    .append(variableType)
                    .append(";\n");
            this.sharedLogic = builder.toString();
            return;
        }

        // 2️⃣ 如果有 coreStubbedMethods → 构造 mock 方法
        if (involvedMocks == null || involvedMocks.isEmpty()) {
            this.sharedLogic = ""; // 安全兜底
            return;
        }

        MockInfo firstMock = involvedMocks.get(0);
        builder.append(variableType)
                .append(" mock")
                .append(variableType)
                .append("() {\n");


        for (StatementInfo stmt : firstMock.statements) {
            String type = stmt.type != null ? stmt.type : "";
            String stubMethod = stmt.stubbedMethod != null ? stmt.stubbedMethod : "";

            // 满足条件的语句：CREATION 或 STUBBING 且 stubbedMethod 属于 coreStubbedMethods
            if ("CREATION".equals(type)) {
                builder.append("    ")
                        .append(stmt.code.trim())
                        .append("\n");
                continue;
            }
            if ("STUBBING".equals(type) && coreStubbedMethods.contains(stubMethod)) {
                builder.append("    ")
                        .append(stmt.code.trim())
                        .append("\n");
            }
        }

        builder.append("    return ")
                .append(firstMock.variableName)
                .append(";\n}\n");

        this.sharedLogic = builder.toString();
    }

}
