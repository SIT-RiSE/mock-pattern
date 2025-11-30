package edu.mock.mockpattern;

import java.util.*;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.FieldAccessExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.NameExpr;

/**
 * Analyzes class and package-level context, and provides utility methods
 * for mock detection and type resolution.
 */
public class MockAnalyzer {
    private final String filePath;
    private String packageName;
    private String className;

    private List<MockInfo> globalVariables = new ArrayList<>();
    private List<MockInfo> finalMocks = new ArrayList<>();

    public MockAnalyzer(String filePath) {
        this.filePath = filePath;
    }

    public void extractPackageName(CompilationUnit cu) {
        this.packageName = cu.getPackageDeclaration()
                .map(pd -> pd.getNameAsString())
                .orElse("");
    }

    public void setCurrentClass(ClassOrInterfaceDeclaration clazz) {
        this.className = clazz.getNameAsString();

        // Step 1: 扫描“全局变量”(字段)
        scanGlobalVariables(clazz);
        // Step 2: 扫描方法
        scanMethods(clazz);
        // 此时所有方法扫描完毕
        // Step 3: 检查 globalVariables 的 statements 是否含 mock 相关内容
        // 将 methodVariables 中的 MockInfo 合并到 globalVariables
        for (MockInfo mockInfo : globalVariables) {
            boolean hasMockUsage = mockInfo.statements.stream().anyMatch(stmt -> stmt.isMockRelated);
            if (hasMockUsage) {
                boolean exists = finalMocks.stream().anyMatch(existing -> existing.isEqual(mockInfo));
                if (!exists) {                    
                    mockInfo.checkMockPatternLevel();
                    finalMocks.add(mockInfo);
                }
            }
        }
    }

    private void scanGlobalVariables(ClassOrInterfaceDeclaration clazz) {
        clazz.getFields().forEach(field -> {
            field.getVariables().forEach(variable -> {
                MockInfo mockInfo = new MockInfo();
                mockInfo.variableName = variable.getNameAsString();
                mockInfo.variableType = variable.getType().asString();


                mockInfo.classContext.packageName = this.packageName;
                mockInfo.classContext.filePath = this.filePath;
                mockInfo.classContext.className = this.className;
                mockInfo.isGlobal = true; // 标记为全局变量

                StatementInfo statementInfo = new StatementInfo();
                statementInfo.code = field.toString();
                statementInfo.line = field.getBegin().map(pos -> pos.line).orElse(-1);
                statementInfo.locationContext.methodName = field.getMetaModel().getTypeName();
                statementInfo.locationContext.methodAnnotations = new ArrayList<>();
                statementInfo.type = "FIELD_DECLARATION"; // 默认类型

                // 1. Check annotations
                field.getAnnotations().forEach(annotation -> {
                    String annotationName = annotation.getNameAsString().toLowerCase();
                    if (annotationName.equals("mock")) {
                        statementInfo.type = "CREATION";
                        statementInfo.isMockRelated = true;
                    } else if (annotationName.equals("spy")) {
                        statementInfo.type = "CREATION";
                        statementInfo.isMockRelated = true;
                    }
                    statementInfo.locationContext.methodAnnotations.add(annotation.getNameAsString());
                });

                // 2. 检查变量初始化（mock、spy 或普通初始化）
                if (variable.getInitializer().isPresent()) {
                    Expression initializer = variable.getInitializer().get();
                    if (CreationAnalyzer.isMockCreation(initializer)) {
                        statementInfo.type = "CREATION";
                        statementInfo.isMockRelated = true;
                    } else if (CreationAnalyzer.isSpyCreation(initializer)) {
                        statementInfo.type = "CREATION";
                        statementInfo.isMockRelated = true;
                    } else if (!statementInfo.isMockRelated) {
                        statementInfo.type = "FIELD_INITIALIZATION"; // 普通赋值（无 @Mock/@Spy 注解）
                    }
                }

                mockInfo.statements.add(statementInfo);
                globalVariables.add(mockInfo);
            });
        });
    }

    private void scanMethods(ClassOrInterfaceDeclaration clazz) {
        clazz.getMethods().forEach(method -> {
            String methodName = method.getNameAsString();
            List<String> methodAnnotations = new ArrayList<>();
            String methodRawCode = method.toString();
            method.getAnnotations().forEach(annotation -> methodAnnotations.add(annotation.getNameAsString()));

            List<MockInfo> methodVariables = new ArrayList<>();

            method.getBody().ifPresent(body -> {
                body.getStatements().forEach(statement -> {
                    StatementInfo statementInfo = new StatementInfo();
                    statementInfo.code = statement.toString();
                    statementInfo.line = statement.getBegin().map(pos -> pos.line).orElse(-1);
                    statementInfo.locationContext.methodName = methodName;
                    statementInfo.locationContext.methodAnnotations = methodAnnotations;
                    statementInfo.locationContext.methodRawCode = methodRawCode;

                    // Analyze the statement
                    if (statement.isExpressionStmt()) {
                        var expression = statement.asExpressionStmt().getExpression();

                        // Handle variable declarations
                        if (expression.isVariableDeclarationExpr()) {
                            expression.asVariableDeclarationExpr().getVariables().forEach(variable -> {
                                MockInfo mockInfo = new MockInfo();
                                mockInfo.variableName = variable.getNameAsString();
                                mockInfo.variableType = variable.getType().asString();
                                mockInfo.classContext.packageName = this.packageName;


                                if (variable.getInitializer().isPresent()) {
                                    var initializer = variable.getInitializer().get();
                                    if (CreationAnalyzer.isMockCreation(initializer)) {
                                        statementInfo.type = "CREATION";
                                        statementInfo.isMockRelated = true;
                                    } else if (CreationAnalyzer.isSpyCreation(initializer)) {
                                        statementInfo.type = "CREATION";
                                        statementInfo.isMockRelated = true;
                                    } else {
                                        statementInfo.type = "METHOD_VARIABLE_INITIALIZATION";
                                    }
                                } else {
                                    statementInfo.type = "METHOD_VARIABLE_DECLARATION";
                                }

                                mockInfo.statements.add(statementInfo);
                                methodVariables.add(mockInfo);
                            });
                        }

                        // Handle assignments
                        else if (expression.isAssignExpr()) {
                            var assignExpr = expression.asAssignExpr();
                            String targetName = assignExpr.getTarget().toString();

                            if (CreationAnalyzer.isMockCreation(assignExpr.getValue())) {
                                statementInfo.type = "CREATION";
                                statementInfo.isMockRelated = true;
                            } else if (CreationAnalyzer.isSpyCreation(assignExpr.getValue())) {
                                statementInfo.type = "CREATION";
                                statementInfo.isMockRelated = true;
                            } else {
                                statementInfo.type = "ASSIGNMENT";
                            }

                            // Check if the target is in methodVariables or globalVariables
                            addStatementToMockInfo(targetName, statementInfo, methodVariables, globalVariables,
                                    expression);
                        }

                        // Handle verification
                        // Optional<String> verifyTargetOpt = getVerificationTargetVariable(expression);
                        else if (getVerificationTargetVariable(expression).isPresent()) {
                            String mockTarget = getVerificationTargetVariable(expression).get();
                            statementInfo.type = "VERIFICATION";
                            statementInfo.isMockRelated = true;

                            addStatementToMockInfo(mockTarget, statementInfo, methodVariables, globalVariables,
                                    expression);
                        } else {

                            // 尝试提取 stubbing 目标 mock 变量
                            Optional<String> mockTargetOpt = StubbingAnalyzer.getStubbingTargetVariable(expression);

                            if (mockTargetOpt.isPresent()) {                                
                                Optional<String> stubbedMethodOpt = StubbingAnalyzer.getStubbedMethodName(expression);
                                String mockTarget = mockTargetOpt.get();
                                String stubbedMethod = stubbedMethodOpt.orElse("unknownMethod");
                                statementInfo.type = "STUBBING";
                                statementInfo.isMockRelated = true;
                                statementInfo.stubbedMethod = stubbedMethod;
                                // 添加 statementInfo 到对应的 MockInfo（先查 methodVariables，再查 globalVariables）
                                addStatementToMockInfo(mockTarget, statementInfo, methodVariables, globalVariables,
                                        expression);
                            }

                            // 非 stubbing、非 verify 的普通表达式
                            Set<String> allVars = extractAllVariableNames(expression);
                            if (!allVars.isEmpty()) {
                                statementInfo.type = "REFERENCE";

                                statementInfo.isMockRelated = false;
                                addStatementToMatchingMockInfos(allVars, statementInfo, methodVariables,
                                        globalVariables);
                            }
                        }

                    }
                });
            });

            // 将 methodVariables 中的 MockInfo 合并到 globalVariables
            for (MockInfo mockInfo : methodVariables) {
                boolean hasMockUsage = mockInfo.statements.stream().anyMatch(stmt -> stmt.isMockRelated);
                if (hasMockUsage) {
                    boolean exists = finalMocks.stream().anyMatch(existing -> existing.isEqual(mockInfo));
                    if (!exists) {
                        mockInfo.checkMockPatternLevel();
                        finalMocks.add(mockInfo);
                    }
                }
            }

        });
    }

    /**
     * 将 statementInfo 添加到对应的 MockInfo 中
     */
    private void addStatementToMockInfo(String mockTarget,
            StatementInfo rawstatementInfo,
            List<MockInfo> methodVariables,
            List<MockInfo> globalVariables,
            Expression expressionForAbstract) {

        StatementInfo statementInfo = rawstatementInfo.copy();

        // 先查局部变量
        Optional<MockInfo> localMockOpt = methodVariables.stream()
                .filter(var -> var.variableName.equals(mockTarget))
                .findFirst();

        if (localMockOpt.isPresent()) {
            MockInfo mock = localMockOpt.get();


            if (!isDuplicateStatement(mock, statementInfo)) {
                mock.statements.add(statementInfo);
            }
            return;
        }

        // 再查全局变量
        Optional<MockInfo> globalMockOpt = globalVariables.stream()
                .filter(var -> var.variableName.equals(mockTarget))
                .findFirst();

        if (globalMockOpt.isPresent()) {
            MockInfo mock = globalMockOpt.get();



            if (!isDuplicateStatement(mock, statementInfo)) {
                mock.statements.add(statementInfo);
            }
        }
    }

    /**
     * 判断是否是 verification 调用，并提取 verify 的 mock 变量名
     * 示例：verify(service).foo() ➜ 提取 service
     */
    private Optional<String> getVerificationTargetVariable(Expression expr) {
        if (!expr.isMethodCallExpr())
            return Optional.empty();

        try {
            MethodCallExpr current = expr.asMethodCallExpr();

            while (true) {
                if (current.getNameAsString().equals("verify")) {
                    if (!current.getArguments().isEmpty()) {
                        Expression arg = current.getArgument(0);
                        String varName = StubbingAnalyzer.extractVariableName(arg);
                        if (varName != null) {
                            return Optional.of(varName);
                        }
                    }
                    break;
                }

                // 继续向上追踪 scope
                if (current.getScope().isPresent() && current.getScope().get().isMethodCallExpr()) {
                    current = current.getScope().get().asMethodCallExpr();
                } else {
                    break;
                }
            }

        } catch (Exception e) {
            // 解析失败容错
        }

        return Optional.empty();
    }

    /**
     * 检查是否已有相同 statementInfo（三项内容相同）
     */
    private boolean isDuplicateStatement(MockInfo mockInfo, StatementInfo newInfo) {
        return mockInfo.statements.stream().anyMatch(existing -> existing.code.equals(newInfo.code) &&
                existing.line == newInfo.line &&
                existing.code.equals(newInfo.code));
    }

    private void addStatementToMatchingMockInfos(Set<String> varNames,
            StatementInfo statementInfo,
            List<MockInfo> methodVariables,
            List<MockInfo> globalVariables) {
        for (String varName : varNames) {
            methodVariables.stream()
                    .filter(mock -> mock.variableName.equals(varName))
                    .filter(mock -> !isDuplicateStatement(mock, statementInfo))
                    .forEach(mock -> mock.statements.add(statementInfo));

            globalVariables.stream()
                    .filter(mock -> mock.variableName.equals(varName))
                    .filter(mock -> !isDuplicateStatement(mock, statementInfo))
                    .forEach(mock -> mock.statements.add(statementInfo));
        }
    }

    /**
     * 递归提取表达式中所有变量名（NameExpr 和 FieldAccessExpr）
     * 示例：foo(bar, obj.baz) ➜ bar, baz
     */
    private Set<String> extractAllVariableNames(Expression expr) {
        Set<String> variableNames = new HashSet<>();

        expr.walk(node -> {
            if (node instanceof NameExpr) {
                variableNames.add(((NameExpr) node).getNameAsString());
            } else if (node instanceof FieldAccessExpr) {
                variableNames.add(((FieldAccessExpr) node).getNameAsString());
            }
        });

        return variableNames;
    }

    public List<MockInfo> getFinalMocks() {
        return finalMocks;
    }
}
