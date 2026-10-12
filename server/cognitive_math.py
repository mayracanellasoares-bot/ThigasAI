"""Verificador aritmético restrito; não executa código do usuário.

Usado somente para perguntas que sejam uma expressão aritmética isolada.
Não representa treinamento nem raciocínio geral do modelo neural.
"""
from __future__ import annotations

import ast
from decimal import Decimal, localcontext
from fractions import Fraction
import re

PREFIX = re.compile(
    r"^\s*(?:(?:quanto\s+é|calcule|calcular|resolva|"
    r"qual\s+é\s+o\s+(?:resultado|valor)\s+de)\s*:?\s*)?"
    r"(?P<expr>[\d\s+*/().,\-^×÷]+)\s*[?!]?\s*$",
    re.IGNORECASE,
)
MAX_EXPRESSION_LENGTH = 120
MAX_ABSOLUTE_COMPONENT = 10**18


def _bounded(value: Fraction) -> Fraction:
    if abs(value.numerator) > MAX_ABSOLUTE_COMPONENT or value.denominator > MAX_ABSOLUTE_COMPONENT:
        raise ValueError("Resultado fora do intervalo permitido")
    return value


def _evaluate(node: ast.AST, expression: str, depth: int = 0) -> Fraction:
    if depth > 16:
        raise ValueError("Expressão muito aninhada")
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        raw = ast.get_source_segment(expression, node)
        if raw is None or 'e' in raw.lower():
            raise ValueError("Formato numérico não permitido")
        return _bounded(Fraction(Decimal(raw)))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        item = _evaluate(node.operand, expression, depth + 1)
        return _bounded(-item if isinstance(node.op, ast.USub) else item)
    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left, expression, depth + 1)
        right = _evaluate(node.right, expression, depth + 1)
        if isinstance(node.op, ast.Add):
            return _bounded(left + right)
        if isinstance(node.op, ast.Sub):
            return _bounded(left - right)
        if isinstance(node.op, ast.Mult):
            return _bounded(left * right)
        if isinstance(node.op, ast.Div):
            return _bounded(left / right)
        if isinstance(node.op, ast.Pow) and right.denominator == 1 and 0 <= right.numerator <= 8:
            return _bounded(left ** right.numerator)
    raise ValueError("Operação não autorizada")


def _format_fraction(value: Fraction) -> str:
    denominator = value.denominator
    while denominator % 2 == 0:
        denominator //= 2
    while denominator % 5 == 0:
        denominator //= 5
    with localcontext() as ctx:
        ctx.prec = 36
        if denominator == 1:
            decimal = format(Decimal(value.numerator) / Decimal(value.denominator), 'f')
            return decimal.rstrip('0').rstrip('.').replace('.', ',') if '.' in decimal else decimal
        approx = format(Decimal(value.numerator) / Decimal(value.denominator), '.12g').replace('.', ',')
    return f"{value.numerator}/{value.denominator} (aprox. {approx})"


def solve_simple_arithmetic(question: str) -> str | None:
    """Retorna resultado comprovado ou None para perguntas fora do escopo.

    Não analisa problemas de texto, expressões incompletas ou instruções de código.
    """
    if not isinstance(question, str) or len(question) > 180:
        return None
    match = PREFIX.fullmatch(question)
    if not match:
        return None
    expression = match.group('expr').strip().replace('×', '*').replace('÷', '/').replace('^', '**')
    expression = re.sub(r'(?<=\d),(?=\d)', '.', expression)
    if not expression or len(expression) > MAX_EXPRESSION_LENGTH:
        return None
    if not re.search(r'\d', expression):
        return None
    try:
        parsed = ast.parse(expression, mode='eval')
        result = _evaluate(parsed.body, expression)
    except ZeroDivisionError:
        return "Divisão por zero não está definida."
    except (SyntaxError, ValueError, ArithmeticError, OverflowError, RecursionError, TypeError):
        return None
    return f"Resultado verificado: **{_format_fraction(result)}**."
