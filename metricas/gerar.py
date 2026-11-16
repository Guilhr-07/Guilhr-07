#!/usr/bin/env python3
"""Conta as métricas do perfil direto no código das APIs públicas.

Nada aqui é digitado à mão: endpoint é anotação @*Mapping em src/main, teste é
anotação @Test em src/test, e o estado do CI vem da última execução no main.

  python metricas/gerar.py --saida saida/      gera metricas.svg e metricas.json
  python metricas/gerar.py --conferir README.md   falha se o README discordar do código

O texto do painel vira contorno (fontTools), porque SVG dentro de <img> não
carrega webfont: no GitHub ele sairia na fonte do sistema de quem abre.

Precisa de `git`, `gh` e `pip install fonttools`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from functools import lru_cache
from html import escape
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

AQUI = Path(__file__).parent
ENDPOINT = re.compile(r"^\s*@(Get|Post|Put|Patch|Delete)Mapping\b", re.M)
TESTE = re.compile(r"^\s*@(Test|ParameterizedTest|RepeatedTest)\b", re.M)

# Cores da marca do portfólio (tema escuro, o mesmo do banner).
FUNDO, SUPERFICIE, TEXTO, TEXTO2 = "#15110a", "#1e1911", "#f2ecdc", "#a89f8a"
ACENTO, LINHA, OK, ERRO = "#fbe311", "#2f281c", "#9bd49b", "#f08a7e"
CORES_LING = [ACENTO, TEXTO, "#8c8369", "#5a5340"]


@lru_cache
def fonte(peso: int):
    f = TTFont(AQUI / "fontes" / f"MartianMono-{peso}.woff")
    return f, f.getBestCmap(), f.getGlyphSet(), f["head"].unitsPerEm


def largura(texto: str, tam: float, peso: int = 400) -> float:
    f, cmap, _, upm = fonte(peso)
    return sum(f["hmtx"][cmap[ord(c)]][0] for c in texto) * tam / upm


def contorno(x: float, y: float, texto, cor: str = TEXTO, tam: float = 13,
             peso: int = 400, ancora: str = "start") -> str:
    """Desenha o texto como <path>, glifo por glifo, na Martian Mono."""
    texto = str(texto)
    f, cmap, glifos, upm = fonte(peso)
    if ancora == "end":
        x -= largura(texto, tam, peso)
    escala, partes, avanco = tam / upm, [], 0.0
    for c in texto:
        if ord(c) not in cmap:
            raise SystemExit(f"a fonte não tem o caractere {c!r} (em {texto!r})")
        nome = cmap[ord(c)]
        caneta = SVGPathPen(glifos)
        glifos[nome].draw(caneta)
        d = caneta.getCommands()
        if d:
            partes.append(f'<path transform="translate({x + avanco * escala:.2f} {y}) '
                          f'scale({escala:.5f} {-escala:.5f})" d="{d}"/>')
        avanco += f["hmtx"][nome][0]
    return f'<g fill="{cor}">' + "".join(partes) + "</g>"


def rodar(*cmd: str) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def api(caminho: str):
    """Chama a API do GitHub pelo gh. Devolve None se falhar: métrica sem dado
    aparece como "sem dado", nunca como número inventado."""
    try:
        return json.loads(rodar("gh", "api", caminho))
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return None


def contar(pasta: Path, padrao: re.Pattern) -> int:
    if not pasta.is_dir():
        return 0
    return sum(len(padrao.findall(f.read_text(encoding="utf-8", errors="replace")))
               for f in pasta.rglob("*.java"))


def medir(item: dict, base: Path) -> dict:
    repo = item["repo"]
    destino = base / repo.split("/")[1]
    rodar("git", "clone", "--quiet", "--depth", "1", f"https://github.com/{repo}", str(destino))
    ultimo = rodar("git", "-C", str(destino), "log", "-1", "--format=%cs").strip()

    ci = {"estado": "sem dado", "data": None}
    execs = api(f"repos/{repo}/actions/runs?branch=main&status=completed&per_page=1")
    if execs and execs.get("workflow_runs"):
        r = execs["workflow_runs"][0]
        ci = {"estado": "passou" if r["conclusion"] == "success" else "falhou",
              "data": r["created_at"][:10]}

    return {
        "repo": repo,
        "nome": item["nome"],
        "endpoints": contar(destino / "src" / "main", ENDPOINT),
        "testes": contar(destino / "src" / "test", TESTE),
        "ci": ci,
        "ultimo_commit": ultimo,
        "linguagens": api(f"repos/{repo}/languages") or {},
    }


def coletar() -> dict:
    itens = json.loads((AQUI / "repos.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        apis = [medir(i, Path(tmp)) for i in itens]
    bytes_ling: dict[str, int] = {}
    for a in apis:
        for nome, n in a["linguagens"].items():
            bytes_ling[nome] = bytes_ling.get(nome, 0) + n
    total = sum(bytes_ling.values()) or 1
    ordenadas = sorted(bytes_ling.items(), key=lambda kv: -kv[1])
    linguagens = [{"nome": n, "pct": round(100 * b / total, 1)} for n, b in ordenadas[:3]]
    resto = round(100 - sum(l["pct"] for l in linguagens), 1)
    if len(ordenadas) > 3 and resto > 0:
        linguagens.append({"nome": "outras", "pct": resto})
    return {
        "conferido_em": dt.date.today().isoformat(),
        "endpoints": sum(a["endpoints"] for a in apis),
        "testes": sum(a["testes"] for a in apis),
        "ci_verde": sum(a["ci"]["estado"] == "passou" for a in apis),
        "apis": [{k: v for k, v in a.items() if k != "linguagens"} for a in apis],
        "linguagens": linguagens,
    }


def br(data: str | None) -> str:
    return f"{data[8:10]}/{data[5:7]}/{data[:4]}" if data else "sem dado"


def svg(d: dict) -> str:
    L, M = 840, 32  # largura e margem
    n = len(d["apis"])
    t = contorno
    p: list[str] = []

    p.append(t(M, 44, "MEDIDO NO CÓDIGO DAS TRÊS APIS", TEXTO2, 11))
    p.append(t(L - M, 44, f"conferido em {br(d['conferido_em'])}", TEXTO2, 11, ancora="end"))

    # Três números grandes, divididos por linha, como a faixa do hero do site.
    ci_txt = "APIs com CI passando" if d["ci_verde"] == n else f"de {n} APIs com CI passando"
    celulas = [(d["endpoints"], "endpoints REST"), (d["testes"], "testes de integração"),
               (d["ci_verde"], ci_txt)]
    larg = (L - 2 * M) / 3
    p.append(f'<line x1="{M}" y1="62" x2="{L - M}" y2="62" stroke="{TEXTO}" stroke-width="1"/>')
    for i, (valor, rotulo) in enumerate(celulas):
        x = M + i * larg
        if i:
            p.append(f'<line x1="{x}" y1="62" x2="{x}" y2="146" stroke="{LINHA}"/>')
        p.append(t(x + (16 if i else 0), 112, valor, ACENTO, 38, 500))
        p.append(t(x + (16 if i else 0), 134, rotulo, TEXTO, 12))
    p.append(f'<line x1="{M}" y1="146" x2="{L - M}" y2="146" stroke="{LINHA}"/>')

    # Uma linha por API.
    cols = [M, 330, 430, 520, L - M]
    y = 176
    for x, rot, anc in [(cols[0], "API", "start"), (cols[1], "ENDPOINTS", "end"),
                        (cols[2], "TESTES", "end"), (cols[3] - 60, "CI NO MAIN", "start"),
                        (cols[4], "ÚLTIMO COMMIT", "end")]:
        p.append(t(x, y, rot, TEXTO2, 10, ancora=anc))
    for a in d["apis"]:
        y += 30
        cor_ci = {"passou": OK, "falhou": ERRO}.get(a["ci"]["estado"], TEXTO2)
        ci = a["ci"]["estado"] + (f" em {br(a['ci']['data'])}" if a["ci"]["data"] else "")
        p.append(t(cols[0], y, a["nome"], TEXTO, 13, 500))
        p.append(t(cols[1], y, a["endpoints"], TEXTO, 13, ancora="end"))
        p.append(t(cols[2], y, a["testes"], TEXTO, 13, ancora="end"))
        p.append(f'<rect x="{cols[3] - 60}" y="{y - 9}" width="8" height="8" fill="{cor_ci}"/>')
        p.append(t(cols[3] - 46, y, ci, TEXTO, 13))
        p.append(t(cols[4], y, br(a["ultimo_commit"]), TEXTO2, 13, ancora="end"))
        p.append(f'<line x1="{M}" y1="{y + 11}" x2="{L - M}" y2="{y + 11}" stroke="{LINHA}"/>')

    # Barra de linguagens, por bytes de código nos três repositórios.
    y += 44
    if d["linguagens"]:
        p.append(t(M, y, "LINGUAGENS, POR BYTES DE CÓDIGO", TEXTO2, 10))
        y += 12
        x, legenda_x = float(M), M
        legendas = []
        for i, l in enumerate(d["linguagens"]):
            cor = CORES_LING[i % len(CORES_LING)]
            w = (L - 2 * M) * l["pct"] / 100
            p.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w, 1):.1f}" height="8" fill="{cor}"/>')
            x += w
            rot = f"{l['nome']} {str(l['pct']).replace('.', ',')}%"
            legendas.append(f'<rect x="{legenda_x}" y="{y + 20}" width="8" height="8" fill="{cor}"/>'
                            + t(legenda_x + 14, y + 28, rot, TEXTO, 12))
            legenda_x += 14 + largura(rot, 12) + 28
        p.extend(legendas)
        y += 28

    y += 30
    p.append(t(M, y, "Endpoint é anotação @*Mapping, teste é @Test. Script em metricas/gerar.py, roda todo dia.",
               TEXTO2, 11))
    altura = y + 26

    resumo = (f"{d['endpoints']} endpoints REST, {d['testes']} testes de integração, "
              f"{d['ci_verde']} de {n} APIs com CI passando. Conferido em {br(d['conferido_em'])}.")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{altura}" '
            f'viewBox="0 0 {L} {altura}" role="img" aria-label="{escape(resumo)}">\n<title>{escape(resumo)}</title>\n'
            f'<rect width="{L}" height="{altura}" fill="{FUNDO}"/>\n' + "\n".join(p) + "\n</svg>\n")


def conferir(d: dict, readme: Path) -> list[str]:
    """Cada API tem uma linha na tabela do README com o link do repositório e as
    células "N endpoints" e "N testes". Se o código mudou e o texto não, acusa."""
    texto = readme.read_text(encoding="utf-8")
    erros = []
    for a in d["apis"]:
        linha = next((l for l in texto.splitlines() if f"github.com/{a['repo']})" in l and l.startswith("|")), None)
        if linha is None:
            erros.append(f"{a['nome']}: sem linha na tabela do README")
            continue
        for chave, palavra in (("endpoints", "endpoints"), ("testes", "testes")):
            m = re.search(rf"(\d+) {palavra}", linha)
            if not m:
                erros.append(f"{a['nome']}: a linha não diz quantos {palavra}")
            elif int(m.group(1)) != a[chave]:
                erros.append(f"{a['nome']}: README diz {m.group(1)} {palavra}, o código tem {a[chave]}")
    for chave, palavra in (("endpoints", "endpoints"), ("testes", "testes")):
        m = re.search(rf"\*\*(\d+) {palavra}", texto)
        if m and int(m.group(1)) != d[chave]:
            erros.append(f"total: README diz {m.group(1)} {palavra}, o código tem {d[chave]}")
    return erros


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saida", type=Path, help="pasta onde gravar metricas.svg e metricas.json")
    ap.add_argument("--conferir", type=Path, help="README a comparar com o código")
    args = ap.parse_args()
    if not (args.saida or args.conferir):
        ap.error("use --saida, --conferir ou os dois")

    d = coletar()
    if args.saida:
        args.saida.mkdir(parents=True, exist_ok=True)
        (args.saida / "metricas.svg").write_text(svg(d), encoding="utf-8")
        (args.saida / "metricas.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{d['endpoints']} endpoints, {d['testes']} testes, CI passando em {d['ci_verde']} de {len(d['apis'])}")
    if args.conferir:
        erros = conferir(d, args.conferir)
        for e in erros:
            print(f"DIVERGE  {e}", file=sys.stderr)
        if erros:
            return 1
        print("README bate com o código")
    return 0


if __name__ == "__main__":
    sys.exit(main())
