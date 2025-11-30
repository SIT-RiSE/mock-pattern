package edu.mock.mockpattern;

import java.util.*;
import java.util.stream.Collectors;

public class MockCloneInstanceGenerator {

    private static int instanceCounter = 0;

    private final List<MockInfo> mockList;

    /** 构造函数：传入 MockInfo 列表 */
    public MockCloneInstanceGenerator(List<MockInfo> mockList) {
        this.mockList = mockList;
    }

    /** 生成 CloneInstance 列表 */
    public List<CloneInstance> generateCloneInstances() {
        List<CloneInstance> result = new ArrayList<>();

        // 1️⃣ 过滤出 mockPatternLevel = 0 的 MockInfo
        List<MockInfo> level0Mocks = mockList.stream()
                .filter(m -> m.mockPatternLevel == 0)
                .collect(Collectors.toList());

        // 2️⃣ 按 variableType 分组
        Map<String, List<MockInfo>> groupedByType = level0Mocks.stream()
                .collect(Collectors.groupingBy(m -> m.variableType));

        // 3️⃣ 对每个 variableType 进行 clone 检测（占位逻辑）
        for (Map.Entry<String, List<MockInfo>> entry : groupedByType.entrySet()) {
            String mockedClass = entry.getKey();
            List<MockInfo> mocksOfType = entry.getValue();
            // --- 二次分组：根据 stubbedInfo 是否为空 ---
            List<MockInfo> stubbedMocks = new ArrayList<>();
            List<MockInfo> nonStubbedMocks = new ArrayList<>();

            for (MockInfo m : mocksOfType) {
                // 确保 stubbedInfo 已生成（防止未调用）
                if (m.stubbedInfo == null)
                    m.generateStubbedInfo();

                if (m.stubbedInfo != null && !m.stubbedInfo.isEmpty()) {
                    stubbedMocks.add(m);
                } else {
                    nonStubbedMocks.add(m);
                }
            }

            // List<CloneInstance> instancesForType = generateInstancesForType(mockedClass,
            // mocksOfType);
            List<CloneInstance> instancesForType = new ArrayList<>();

            if (!stubbedMocks.isEmpty()) {
                instancesForType.addAll(StubbedClone(mockedClass, stubbedMocks));
            }

            if (!nonStubbedMocks.isEmpty()) {
                instancesForType.addAll(NonStubbedClone(mockedClass, nonStubbedMocks));
            }
            // 4️⃣ 合并结果
            result.addAll(instancesForType);
        }

        return result;
    }

    private List<CloneInstance> StubbedClone(String mockedClass, List<MockInfo> stubbedMocks) {
        List<CloneInstance> instances = new ArrayList<>();

        if (stubbedMocks == null || stubbedMocks.isEmpty()) {
            return instances;
        }

        // 1️⃣ 构建 transactions：每个 MockInfo 的 stubbedInfo 作为一条事务
        List<List<String>> transactions = new ArrayList<>();
        for (MockInfo mock : stubbedMocks) {
            transactions.add(new ArrayList<>(mock.stubbedInfo));
        }

        // 2️⃣ 调用 Apriori 算法，minSupport = 2（可调）
        AprioriMiner miner = new AprioriMiner();
        Map<Set<String>, Set<Integer>> result = miner.mine(transactions, 2);

        // 3️⃣ 排序 key：按 |key| * |value| 降序排列
        List<Map.Entry<Set<String>, Set<Integer>>> sortedList = new ArrayList<>(result.entrySet());
        sortedList.sort((a, b) -> {
            int scoreA = a.getKey().size() * a.getValue().size();
            int scoreB = b.getKey().size() * b.getValue().size();
            return Integer.compare(scoreB, scoreA); // 降序
        });

        // 4️⃣ 记录每个 Mock 是否已被合并
        boolean[] used = new boolean[stubbedMocks.size()];

        // 5️⃣ 遍历每个频繁项集
        for (Map.Entry<Set<String>, Set<Integer>> entry : sortedList) {
            Set<String> coreMethods = new HashSet<>(entry.getKey());
            Set<Integer> indices = new HashSet<>(entry.getValue());

            // 去除已被合并的 mock
            List<Integer> validIndices = new ArrayList<>();
            for (int idx : indices) {
                if (!used[idx]) {
                    validIndices.add(idx);
                }
            }

            // 只保留至少两个未被合并的 mock
            if (validIndices.size() < 2)
                continue;

            // 组建 involvedMocks
            List<MockInfo> involved = new ArrayList<>();
            for (int idx : validIndices) {
                involved.add(stubbedMocks.get(idx));
                used[idx] = true; // 标记为已合并
            }

            // 创建 CloneInstance
            CloneInstance instance = new CloneInstance(
                    instanceCounter++, // instanceId
                    mockedClass, // variableType
                    1, // convertedLevel（构造函数自动计算）
                    new ArrayList<>(coreMethods), // coreStubbedMethods
                    involved // involvedMocks
            );

            instances.add(instance);
        }

        return instances;
    }

    private List<CloneInstance> NonStubbedClone(String mockedClass, List<MockInfo> nonStubbedMocks) {
        List<CloneInstance> instances = new ArrayList<>();

        if (nonStubbedMocks == null || nonStubbedMocks.isEmpty()) {
            return instances;
        }

        // 1️⃣ 按 filePath 分组
        Map<String, List<MockInfo>> groupedByFile = nonStubbedMocks.stream()
                .filter(m -> m.classContext != null && m.classContext.filePath != null)
                .collect(Collectors.groupingBy(m -> m.classContext.filePath));

        // 2️⃣ 每个 filePath 生成一个 CloneInstance（使用构造函数）
        for (Map.Entry<String, List<MockInfo>> entry : groupedByFile.entrySet()) {
            List<MockInfo> mocksInFile = entry.getValue();
            if (mocksInFile.size() >= 2) {
                // 当大于2时，构造 CloneInstance
                CloneInstance instance = new CloneInstance(
                        instanceCounter++, // instanceId
                        mockedClass, // variableType
                        1, // mockPatternLevel （都为 1）
                        new ArrayList<>(), // coreStubbedMethods 为空
                        mocksInFile // involvedMocks
                );
                instances.add(instance);
            }
        }

        return instances;
    }

}
