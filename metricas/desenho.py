"""Desenho das peças do perfil: cores da marca, texto em contorno e moldura.

O texto vira <path> porque SVG dentro de <img> não carrega webfont: no GitHub
ele sairia na fonte do sistema de quem abre. Cada glifo é definido uma vez em
<defs> e reaproveitado com <use>, para o arquivo não crescer a cada letra.
"""
from __future__ import annotations

from functools import lru_cache
from html import escape
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

AQUI = Path(__file__).parent

# Os dois temas do portfólio (globals.css). Um acento só. No claro o amarelo só
# preenche: texto de acento usa a tinta escura, como no site.
TEMAS = {
    "escuro": {
        "fundo": "#15110a", "superficie": "#1e1911", "texto": "#f2ecdc", "texto2": "#a89f8a",
        "acento": "#fbe311", "tinta": "#fbe311", "sobre_acento": "#15110a", "linha": "#2f281c",
        "ok": "#9bd49b", "erro": "#f08a7e",
        "escala": ["#1e1911", "#4a4210", "#857710", "#c4b011", "#fbe311"],
    },
    "claro": {
        "fundo": "#f3f2ee", "superficie": "#eae8e1", "texto": "#1e170c", "texto2": "#5c5546",
        "acento": "#fbe311", "tinta": "#6b5400", "sobre_acento": "#1e170c", "linha": "#d9d5ca",
        "ok": "#2f6b2f", "erro": "#a3261b",
        "escala": ["#e4e1d8", "#f0e491", "#e6cc12", "#a88a00", "#6b5400"],
    },
}

LARGURA, MARGEM, RAIO = 1000, 36, 4
ARQUIVOS = {
    ("mono", 400): "MartianMono-400.woff",
    ("mono", 500): "MartianMono-500.woff",
    ("display", 800): "Bricolage-800.woff",
}

# As três durações do site, e tudo para com prefers-reduced-motion.
CSS_BASE = """
.sobe{animation:sobe 620ms cubic-bezier(.2,.7,.2,1) both}
.surge{animation:surge 320ms ease-out both}
@keyframes sobe{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes surge{from{opacity:0}to{opacity:1}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


@lru_cache
def fonte(familia: str, peso: int):
    f = TTFont(AQUI / "fontes" / ARQUIVOS[(familia, peso)])
    return f, f.getBestCmap(), f.getGlyphSet(), f["head"].unitsPerEm


def largura(texto: str, tam: float, peso: int = 400, familia: str = "mono") -> float:
    f, cmap, _, upm = fonte(familia, peso)
    return sum(f["hmtx"][cmap[ord(c)]][0] for c in str(texto)) * tam / upm


class Peca:
    """Uma imagem SVG. Junta os glifos usados e monta a moldura no fim."""

    def __init__(self, altura: int, resumo: str, tema: str, css: str = ""):
        self.altura, self.resumo, self.css = altura, resumo, css
        self.t = TEMAS[tema]
        self.glifos: dict[str, str] = {}
        self.partes: list[str] = []

    def add(self, *trechos: str) -> None:
        self.partes.extend(trechos)

    def texto(self, x: float, y: float, texto, cor: str | None = None, tam: float = 13,
              peso: int = 400, ancora: str = "start", familia: str = "mono") -> str:
        texto, cor = str(texto), cor or self.t["texto"]
        f, cmap, glifos, upm = fonte(familia, peso)
        if ancora == "end":
            x -= largura(texto, tam, peso, familia)
        elif ancora == "middle":
            x -= largura(texto, tam, peso, familia) / 2
        escala, usos, avanco = tam / upm, [], 0.0
        for c in texto:
            if ord(c) not in cmap:
                raise SystemExit(f"a fonte {familia} não tem o caractere {c!r} (em {texto!r})")
            nome = cmap[ord(c)]
            chave = f"{familia[0]}{peso}-{nome}"
            if chave not in self.glifos:
                caneta = SVGPathPen(glifos)
                glifos[nome].draw(caneta)
                self.glifos[chave] = caneta.getCommands()
            if self.glifos[chave]:
                usos.append(f'<use href="#{chave}" x="{avanco:.0f}"/>')
            avanco += f["hmtx"][nome][0]
        return (f'<g fill="{cor}" transform="translate({x:.2f} {y:.2f}) '
                f'scale({escala:.5f} {-escala:.5f})">' + "".join(usos) + "</g>")

    def linha(self, x1, y1, x2, y2, cor: str | None = None, esp: float = 1) -> str:
        cor = cor or self.t["linha"]
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{cor}" stroke-width="{esp}"/>'

    def ret(self, x, y, w, h, cor: str, extra: str = "") -> str:
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{cor}" {extra}/>'

    def svg(self) -> str:
        defs = "".join(f'<path id="{k}" d="{d}"/>' for k, d in sorted(self.glifos.items()) if d)
        r = escape(self.resumo)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{self.altura}" '
            f'viewBox="0 0 {LARGURA} {self.altura}" role="img" aria-label="{r}">\n'
            f"<title>{r}</title>\n<style>{CSS_BASE}{self.css}</style>\n<defs>{defs}</defs>\n"
            f'<rect x="0.5" y="0.5" width="{LARGURA - 1}" height="{self.altura - 1}" rx="{RAIO}" '
            f'fill="{self.t["fundo"]}" stroke="{self.t["linha"]}"/>\n' + "\n".join(self.partes) + "\n</svg>\n"
        )
