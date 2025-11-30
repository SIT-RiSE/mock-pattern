package edu.mock.mockpattern;


import com.github.javaparser.ast.expr.Expression;

public class CreationAnalyzer {
    public static boolean isMockCreation(Expression expression) {
        if (!expression.isMethodCallExpr())
            return false;

        try {
            String methodName = expression.asMethodCallExpr().getNameAsString();
            return methodName.equals("mock");
        } catch (Exception e) {
            // 解析失败：通常是 UnsolvedSymbolException
            // System.err.println("[WARN] Unable to resolve expression: " + expression);
            return false;
        }
    }

    public static boolean isSpyCreation(Expression expression) {
        if (!expression.isMethodCallExpr())
            return false;

        try {
            String methodName = expression.asMethodCallExpr().getNameAsString();
            return methodName.equals("spy");
        } catch (Exception e) {
            // System.err.println("[WARN] Unable to resolve expression: " + expression);
            return false;
        }
    }

}