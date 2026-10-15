"""Parser de combat logs de World of Warcraft (formato de archivo WoWCombatLog*.txt).

El parser es puro (no toca la base de datos) y está versionado: cada reporte guarda
``PARSER_VERSION`` para poder reprocesarlo cuando cambien las reglas de cálculo.
"""

from app.parser.parser import PARSER_VERSION, ParseResult, parse_lines, parse_text

__all__ = ["PARSER_VERSION", "ParseResult", "parse_lines", "parse_text"]
