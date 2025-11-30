package edu.mock.mockpattern;

import java.util.Optional;

import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.MethodCallExpr;

public class StubbingAnalyzer {
    // 从表达式中提取变量名，例如 mock 对象名
    public static String extractVariableName(Expression expr) {
        if (expr == null)
            return null;

        if (expr.isNameExpr()) {
            return expr.asNameExpr().getNameAsString();
        } else if (expr.isFieldAccessExpr()) {
            return expr.asFieldAccessExpr().getNameAsString();
        } else if (expr.isMethodCallExpr()) {
            return extractVariableName(expr.asMethodCallExpr().getScope().orElse(null));
        }

        return null;
    }

    // 遍历链式调用，找到 when() 或 given()：
    private static Optional<MethodCallExpr> findWhenOrGivenCall(MethodCallExpr call) {
        MethodCallExpr current = call;
        while (true) {
            String methodName = current.getNameAsString();
            if (methodName.equals("when") || methodName.equals("given")) {
                return Optional.of(current);
            }
            if (current.getScope().isPresent() && current.getScope().get().isMethodCallExpr()) {
                current = current.getScope().get().asMethodCallExpr();
            } else {
                break;
            }
        }
        return Optional.empty();
    }

    // 提取 mock 对象名（when/given 的参数）
    private static Optional<String> extractMockFromWhenOrGiven(MethodCallExpr whenOrGivenCall) {
        if (!whenOrGivenCall.getArguments().isEmpty()) {
            Expression arg = whenOrGivenCall.getArgument(0);

            // case 1: when(mock.method())
            if (arg.isMethodCallExpr()) {
                MethodCallExpr innerCall = arg.asMethodCallExpr();
                if (innerCall.getScope().isPresent()) {
                    return Optional.ofNullable(extractVariableName(innerCall.getScope().get()));
                }
            }

            // case 2: when(mock)
            else {
                return Optional.ofNullable(extractVariableName(arg));
            }
        }
        return Optional.empty();
    }

    // 整合判断与提取
    public static Optional<String> getStubbingTargetVariable(Expression expr) {
        if (!expr.isMethodCallExpr())
            return Optional.empty();

        try {
            MethodCallExpr call = expr.asMethodCallExpr();
            Optional<MethodCallExpr> whenOrGivenOpt = findWhenOrGivenCall(call);
            if (whenOrGivenOpt.isPresent()) {
                return extractMockFromWhenOrGiven(whenOrGivenOpt.get());
            }
        } catch (Exception e) {
            // Resolve 失败
        }

        return Optional.empty();
    }

    public static Optional<String> getStubbedMethodName(Expression expr) {
        if (!expr.isMethodCallExpr())
            return Optional.empty();

        try {
            MethodCallExpr call = expr.asMethodCallExpr();
            Optional<MethodCallExpr> whenOrGivenOpt = findWhenOrGivenCall(call);
            if (whenOrGivenOpt.isPresent()) {
                MethodCallExpr whenOrGiven = whenOrGivenOpt.get();
                if (!whenOrGiven.getArguments().isEmpty()) {
                    Expression arg = whenOrGiven.getArgument(0);

                    // case 1: when(mock.method())
                    if (arg.isMethodCallExpr()) {
                        MethodCallExpr innerCall = arg.asMethodCallExpr();
                        return Optional.of(innerCall.getNameAsString());
                    }
                }
            }
        } catch (Exception e) {
            // 忽略解析异常，保持容错
        }

        return Optional.empty();
    }

}