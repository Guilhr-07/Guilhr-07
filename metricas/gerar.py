#!/usr/bin/env python3
"""Gera as peças do perfil a partir de dado real, sem serviço de terceiro.

  cabecalho     quem sou, com o trace da requisição animado
  atividade     calendário de contribuições dos últimos 12 meses e os totais
  tecnologias   a stack por camada, só o que tem código meu
  apis          endpoints, testes e CI das três APIs, contados no código
  projeto-*     um cartão por API, para servir de link ao repositório

Cada peça sai em dois temas (claro e escuro). Nada é digitado à mão: endpoint é
anotação @*Mapping em src/main, teste é @Test em src/test, o CI vem da última
execução no main e as contribuições vêm da API do GitHub.

  python metricas/gerar.py --saida saida/          gera os SVG e o dados.json
  python metricas/gerar.py --conferir README.md    falha se o README discordar do código
  python metricas/gerar.py --saida saida/ --atividade arquivo.json
                                                   usa contribuições de um arquivo (para testar sem rede)

Precisa de `git`, `gh` e `pip install fonttools`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from desenho import LARGURA, MARGEM, Peca, TEMAS, largura

AQUI = Path(__file__).parent
USUARIO = "Guilhr-07"
ENDPOINT = re.compile(r"^\s*@(Get|Post|Put|Patch|Delete)Mapping\b", re.M)
TESTE = re.compile(r"^\s*@(Test|ParameterizedTest|RepeatedTest)\b", re.M)
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

CONSULTA = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""


# ---------------------------------------------------------------- coleta

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
        "resumo": item["resumo"],
        "endpoints": contar(destino / "src" / "main", ENDPOINT),
        "testes": contar(destino / "src" / "test", TESTE),
        "ci": ci,
        "ultimo_commit": ultimo,
        "linguagens": api(f"repos/{repo}/languages") or {},
    }


def coletar_apis() -> dict:
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
    return {
        "endpoints": sum(a["endpoints"] for a in apis),
        "testes": sum(a["testes"] for a in apis),
        "ci_verde": sum(a["ci"]["estado"] == "passou" for a in apis),
        "apis": [{k: v for k, v in a.items() if k != "linguagens"} for a in apis],
        "linguagens": linguagens,
    }


def coletar_atividade() -> dict:
    """Contribuições dos últimos 12 meses, como o próprio perfil mostra. Se a
    API falhar o programa para: é melhor a peça de ontem do que uma vazia."""
    bruto = json.loads(rodar("gh", "api", "graphql", "-f", f"query={CONSULTA}", "-F", f"login={USUARIO}"))
    c = bruto["data"]["user"]["contributionsCollection"]
    return {
        "commits": c["totalCommitContributions"],
        "prs": c["totalPullRequestContributions"],
        "issues": c["totalIssueContributions"],
        "total": c["contributionCalendar"]["totalContributions"],
        "semanas": [[{"data": d["date"], "n": d["contributionCount"], "dia": d["weekday"]}
                     for d in s["contributionDays"]] for s in c["contributionCalendar"]["weeks"]],
    }


def resumir_atividade(a: dict) -> dict:
    """Dias ativos, sequências e dia mais ativo, calculados dos dias."""
    dias = [d for s in a["semanas"] for d in s]
    maior = corrente = 0
    for d in dias:
        corrente = corrente + 1 if d["n"] else 0
        maior = max(maior, corrente)
    # Sequência atual: conta para trás a partir de hoje. Hoje ainda sem
    # contribuição não quebra a sequência; ontem sem, quebra.
    atual, resto = 0, list(reversed(dias))
    if resto and resto[0]["n"] == 0:
        resto = resto[1:]
    for d in resto:
        if not d["n"]:
            break
        atual += 1
    pico = max(dias, key=lambda d: d["n"]) if dias else {"n": 0, "data": None}
    return {"ativos": sum(1 for d in dias if d["n"]), "maior": maior, "atual": atual,
            "pico": pico, "maximo": pico["n"]}


# ---------------------------------------------------------------- desenho

def br(data: str | None, ano: bool = True) -> str:
    if not data:
        return "sem dado"
    return f"{data[8:10]}/{data[5:7]}/{data[:4]}" if ano else f"{data[8:10]}/{data[5:7]}"


def milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def cabecalho(tema: str) -> str:
    css = """
.barra{transform-box:fill-box;transform-origin:left center;animation:enche 9s cubic-bezier(.2,.7,.2,1) infinite both}
@keyframes enche{0%{transform:scaleX(0)}7%{transform:scaleX(1)}92%{transform:scaleX(1);opacity:1}100%{transform:scaleX(1);opacity:.3}}
.pisca{animation:pisca 1.4s steps(2,start) infinite}
@keyframes pisca{to{visibility:hidden}}
"""
    p = Peca(300, "Guilherme Oliveira, dev fullstack em formação, em São Paulo. Java e Spring Boot "
                  "no servidor, React e Next.js na tela. O que acontece depois do clique.", tema, css)
    t, L, M = p.t, LARGURA, 48

    p.add(p.texto(M, 62, "Guilherme Oliveira", tam=15, peso=500))
    x = M + largura("Guilherme Oliveira", 15, 500) + 14
    p.add(p.texto(x, 62, "dev fullstack em formação, São Paulo", t["texto2"], 15))
    p.add(p.texto(L - M, 62, "guilherme-portfolio.dev", t["texto2"], 15, ancora="end"))

    # Título na Bricolage. A segunda metade vai sobre o amarelo, como marca-texto.
    a, b, tam = "O que acontece", "depois do clique", 66
    while largura(a, tam, 800, "display") + largura(b, tam, 800, "display") + 44 > L - 2 * M:
        tam -= 2
    la, lb = largura(a, tam, 800, "display"), largura(b, tam, 800, "display")
    base = 142
    p.add(p.texto(M, base, a, tam=tam, peso=800, familia="display"))
    xb = M + la + 20
    p.add(p.ret(xb, base - tam * 0.86, lb + 24, tam * 1.16, t["acento"], 'class="surge"'))
    p.add(p.texto(xb + 12, base, b, t["sobre_acento"], tam, 800, familia="display"))

    # O trace: sete camadas, uma barra cada, enchendo em sequência.
    camadas = ["interface", "contrato", "domínio", "persistência", "fila", "rota", "resposta"]
    vao, y = 10, 186
    w = (L - 2 * M - vao * (len(camadas) - 1)) / len(camadas)
    for i, nome in enumerate(camadas):
        x = M + i * (w + vao)
        p.add(p.ret(x, y, w, 12, t["superficie"]))
        p.add(p.ret(x, y, w, 12, t["acento"], f'class="barra" style="animation-delay:{i * 380}ms"'))
        p.add(p.texto(x, y + 36, nome, t["texto2"], 13))
        if nome == "resposta":
            p.add(f'<g class="pisca">{p.texto(x + largura("resposta ", 13), y + 36, "200", t["tinta"], 13, 500)}</g>')

    # Embaixo, quem cuida de cada trecho: tela, servidor, tela.
    y2 = y + 58
    trechos = [(0, 1, "tela", "React"), (1, 6, "servidor", "Java, Spring Boot, PostgreSQL"), (6, 7, "tela", "Next.js")]
    for ini, fim, rotulo, quais in trechos:
        x1 = M + ini * (w + vao)
        x2 = M + fim * (w + vao) - vao
        p.add(p.linha(x1, y2, x2, y2))
        p.add(p.texto(x1, y2 + 26, rotulo, tam=13, peso=500))
        p.add(p.texto(x1 + largura(rotulo, 13, 500) + 12, y2 + 26, quais, t["texto2"], 13))
    return p.svg()


def atividade(a: dict, hoje: str, tema: str) -> str:
    r = resumir_atividade(a)
    p = Peca(322, f"{milhar(a['total'])} contribuições no GitHub nos últimos 12 meses, em {r['ativos']} dias. "
                  f"Maior sequência: {r['maior']} dias. Atualizado em {br(hoje)}.", tema)
    t, L, M = p.t, LARGURA, MARGEM

    p.add(p.texto(M, 44, "ATIVIDADE NO GITHUB, ÚLTIMOS 12 MESES", t["texto2"], 11))
    p.add(p.texto(L - M, 44, f"atualizado em {br(hoje)}", t["texto2"], 11, ancora="end"))
    p.add(p.linha(M, 60, L - M, 60, t["texto"]))

    celulas = [(milhar(a["total"]), "contribuições"), (r["ativos"], "dias ativos"),
               (r["atual"], "dias seguidos agora"), (r["maior"], "maior sequência, em dias")]
    larg = (L - 2 * M) / 4
    for i, (valor, rotulo) in enumerate(celulas):
        x = M + i * larg
        if i:
            p.add(p.linha(x, 60, x, 132))
        p.add(f'<g class="sobe" style="animation-delay:{i * 90}ms">'
              + p.texto(x + (16 if i else 0), 104, valor, t["tinta"], 32, 500)
              + p.texto(x + (16 if i else 0), 124, rotulo, tam=11.5) + "</g>")
    p.add(p.linha(M, 132, L - M, 132))

    # Calendário: uma coluna por semana, domingo em cima.
    passo, lado, x0, y0 = 16.6, 12.6, M + 44, 168
    for linha_i, nome in ((1, "seg"), (3, "qua"), (5, "sex")):
        p.add(p.texto(M, y0 + linha_i * passo + 10, nome, t["texto2"], 10.5))
    mes_anterior = None
    for i, semana in enumerate(a["semanas"]):
        x = x0 + i * passo
        mes = int(semana[0]["data"][5:7])
        if mes != mes_anterior and i < len(a["semanas"]) - 1:
            if mes_anterior is not None or semana[0]["data"][8:10] <= "07":
                p.add(p.texto(x, y0 - 10, MESES[mes - 1], t["texto2"], 10.5))
            mes_anterior = mes
        quadros = []
        for d in semana:
            nivel = 0 if not d["n"] else min(4, 1 + int(3 * math.sqrt(d["n"] / r["maximo"])))
            quadros.append(f'<rect x="{x:.1f}" y="{y0 + d["dia"] * passo:.1f}" width="{lado}" height="{lado}" '
                           f'rx="2" fill="{t["escala"][nivel]}"/>')
        p.add(f'<g class="surge" style="animation-delay:{300 + i * 16}ms">' + "".join(quadros) + "</g>")

    y = y0 + 7 * passo + 22
    partes = [f"{milhar(a['commits'])} commits", f"{milhar(a['prs'])} pull requests", f"{milhar(a['issues'])} issues"]
    if r["pico"]["data"]:
        partes.append(f"dia mais ativo: {br(r['pico']['data'], ano=False)}, com {r['pico']['n']}")
    p.add(p.texto(M, y, ", ".join(partes), t["texto2"], 11))
    x = L - M - largura("mais", 10.5)
    p.add(p.texto(x, y, "mais", t["texto2"], 10.5))
    for cor in reversed(t["escala"]):
        x -= 16
        p.add(f'<rect x="{x:.1f}" y="{y - 10}" width="11" height="11" rx="2" fill="{cor}"/>')
    p.add(p.texto(x - 8, y, "menos", t["texto2"], 10.5, ancora="end"))
    return p.svg()


def icone(p: Peca, icones: dict, nome: str, x: float, y: float, cor: str, tam: float = 15) -> str:
    """Ícone da tecnologia (Simple Icons, 24x24). Sem ícone, um quadrado."""
    if nome in icones:
        return (f'<path fill="{cor}" transform="translate({x:.1f} {y - tam + 2:.1f}) '
                f'scale({tam / 24:.4f})" d="{icones[nome]}"/>')
    return f'<rect x="{x + 4:.1f}" y="{y - tam + 6:.1f}" width="{tam - 8}" height="{tam - 8}" fill="{cor}"/>'


def tecnologias(tema: str) -> str:
    stack = json.loads((AQUI / "stack.json").read_text(encoding="utf-8"))
    icones = json.loads((AQUI / "icones.json").read_text(encoding="utf-8"))
    todas = ", ".join(i for c in stack["camadas"] for i in c["itens"])
    p = Peca(336, f"Tecnologias que eu uso, por camada: {todas}. Também uso "
                  f"{', '.join(stack['tambem'])}. Estudando: {', '.join(stack['estudando'])}.", tema)
    t, L, M = p.t, LARGURA, MARGEM

    p.add(p.texto(M, 44, "TECNOLOGIAS, POR CAMADA", t["texto2"], 11))
    p.add(p.texto(L - M, 44, "só o que tem código meu por trás", t["texto2"], 11, ancora="end"))
    p.add(p.linha(M, 60, L - M, 60, t["texto"]))

    larg = (L - 2 * M) / len(stack["camadas"])
    for i, camada in enumerate(stack["camadas"]):
        x = M + i * larg + (18 if i else 0)
        if i:
            p.add(p.linha(M + i * larg, 60, M + i * larg, 232))
        grupo = [p.texto(x, 92, camada["nome"].upper(), t["tinta"], 11.5, 500)]
        for j, item in enumerate(camada["itens"]):
            y = 124 + j * 25
            grupo.append(icone(p, icones, item, x, y, t["texto2"]))
            grupo.append(p.texto(x + 25, y, item, tam=13))
        p.add(f'<g class="sobe" style="animation-delay:{i * 110}ms">' + "".join(grupo) + "</g>")
    p.add(p.linha(M, 232, L - M, 232))

    for k, (rotulo, itens, cor) in enumerate((("TAMBÉM USO", stack["tambem"], t["texto"]),
                                              ("ESTUDANDO, AINDA SEM CÓDIGO", stack["estudando"], t["texto2"]))):
        y = 266 + k * 36
        p.add(p.texto(M, y, rotulo, t["texto2"], 11))
        x = M + 250
        for item in itens:
            p.add(icone(p, icones, item, x, y, t["texto2"]))
            p.add(p.texto(x + 24, y, item, cor, 13))
            x += 24 + largura(item, 13) + 30
    return p.svg()


def apis(d: dict, hoje: str, tema: str) -> str:
    n = len(d["apis"])
    p = Peca(214, f"{d['endpoints']} endpoints REST, {d['testes']} testes de integração, "
                  f"{d['ci_verde']} de {n} APIs com CI passando. Conferido em {br(hoje)}.", tema)
    t, L, M = p.t, LARGURA, MARGEM

    p.add(p.texto(M, 44, "MEDIDO NO CÓDIGO DAS TRÊS APIS", t["texto2"], 11))
    p.add(p.texto(L - M, 44, f"conferido em {br(hoje)}", t["texto2"], 11, ancora="end"))
    p.add(p.linha(M, 60, L - M, 60, t["texto"]))

    ci_txt = "APIs com CI passando" if d["ci_verde"] == n else f"de {n} APIs com CI passando"
    celulas = [(d["endpoints"], "endpoints REST"), (d["testes"], "testes de integração"), (d["ci_verde"], ci_txt)]
    larg = (L - 2 * M) / 3
    for i, (valor, rotulo) in enumerate(celulas):
        x = M + i * larg
        if i:
            p.add(p.linha(x, 60, x, 132))
        p.add(f'<g class="sobe" style="animation-delay:{i * 90}ms">'
              + p.texto(x + (16 if i else 0), 104, valor, t["tinta"], 32, 500)
              + p.texto(x + (16 if i else 0), 124, rotulo, tam=11.5) + "</g>")
    p.add(p.linha(M, 132, L - M, 132))

    # Linguagens, por bytes de código nos três repositórios.
    y, x = 160, float(M)
    cores = [t["acento"], t["texto"], t["texto2"]]
    legenda_x = M
    for i, l in enumerate(d["linguagens"]):
        w = (L - 2 * M) * l["pct"] / 100
        p.add(p.ret(x, y, max(w, 1), 8, cores[i % 3]))
        x += w
        rot = f"{l['nome']} {str(l['pct']).replace('.', ',')}%"
        p.add(p.ret(legenda_x, y + 22, 9, 9, cores[i % 3]))
        p.add(p.texto(legenda_x + 16, y + 31, rot, tam=11.5))
        legenda_x += 16 + largura(rot, 11.5) + 28
    p.add(p.texto(L - M, y + 31, "endpoint é @*Mapping, teste é @Test, contados todo dia",
                  t["texto2"], 11, ancora="end"))
    return p.svg()


def projeto(a: dict, tema: str) -> str:
    """Cartão de uma API. No README cada um é o link para o repositório."""
    ci = a["ci"]["estado"]
    p = Peca(196, f"{a['nome']}: {' '.join(a['resumo'])} {a['endpoints']} endpoints, {a['testes']} testes, "
                  f"CI {ci}. Último commit em {br(a['ultimo_commit'])}.", tema)
    t, M = p.t, 28

    p.add(f'<g class="sobe">' + p.texto(M, 50, a["nome"], tam=26, peso=800, familia="display") + "</g>")
    for i, linha_txt in enumerate(a["resumo"]):
        p.add(p.texto(M, 80 + i * 21, linha_txt, t["texto2"], 13))
    p.add(p.linha(M, 124, LARGURA - M, 124))

    x = M
    for valor, rotulo in ((a["endpoints"], "endpoints"), (a["testes"], "testes")):
        p.add(p.texto(x, 166, valor, t["tinta"], 30, 500))
        x += largura(str(valor), 30, 500) + 10
        p.add(p.texto(x, 166, rotulo, tam=13))
        x += largura(rotulo, 13) + 44
    cor_ci = {"passou": t["ok"], "falhou": t["erro"]}.get(ci, t["texto2"])
    direita = f"último commit em {br(a['ultimo_commit'])}"
    p.add(p.texto(LARGURA - M, 166, direita, t["texto2"], 13, ancora="end"))
    xci = LARGURA - M - largura(direita, 13) - 40 - largura(f"CI {ci}", 13)
    p.add(p.ret(xci - 18, 155, 11, 11, cor_ci))
    p.add(p.texto(xci, 166, f"CI {ci}", tam=13))
    return p.svg()


# ---------------------------------------------------------------- conferência

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
        for chave in ("endpoints", "testes"):
            m = re.search(rf"(\d+) {chave}", linha)
            if not m:
                erros.append(f"{a['nome']}: a linha não diz quantos {chave}")
            elif int(m.group(1)) != a[chave]:
                erros.append(f"{a['nome']}: README diz {m.group(1)} {chave}, o código tem {a[chave]}")
    for chave in ("endpoints", "testes"):
        m = re.search(rf"\*\*(\d+) {chave}", texto)
        if m and int(m.group(1)) != d[chave]:
            erros.append(f"total: README diz {m.group(1)} {chave}, o código tem {d[chave]}")
    return erros


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saida", type=Path, help="pasta onde gravar os SVG e o dados.json")
    ap.add_argument("--conferir", type=Path, help="README a comparar com o código")
    ap.add_argument("--atividade", type=Path, help="JSON de contribuições, no lugar da API")
    args = ap.parse_args()
    if not (args.saida or args.conferir):
        ap.error("use --saida, --conferir ou os dois")

    d = coletar_apis()
    if args.saida:
        hoje = dt.date.today().isoformat()
        a = (json.loads(args.atividade.read_text(encoding="utf-8")) if args.atividade
             else coletar_atividade())
        args.saida.mkdir(parents=True, exist_ok=True)
        pecas = {}
        for tema in TEMAS:
            pecas[f"cabecalho-{tema}"] = cabecalho(tema)
            pecas[f"atividade-{tema}"] = atividade(a, hoje, tema)
            pecas[f"tecnologias-{tema}"] = tecnologias(tema)
            pecas[f"apis-{tema}"] = apis(d, hoje, tema)
            for api_d in d["apis"]:
                pecas[f"projeto-{api_d['repo'].split('/')[1]}-{tema}"] = projeto(api_d, tema)
        for nome, svg in pecas.items():
            (args.saida / f"{nome}.svg").write_text(svg, encoding="utf-8")
        dados = {"conferido_em": hoje, **d, "atividade": {**a, **resumir_atividade(a)}}
        (args.saida / "dados.json").write_text(json.dumps(dados, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{len(pecas)} peças. {d['endpoints']} endpoints, {d['testes']} testes, "
              f"CI passando em {d['ci_verde']} de {len(d['apis'])}. {a['total']} contribuições em 12 meses.")
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
