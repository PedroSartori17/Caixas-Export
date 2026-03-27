#!/usr/bin/env python3
"""
Sistema de Cálculo de Peso e Geração de DXF para Caixas em MDF
==============================================================
Padrão: Caixaria MDF para Exportação

Regras de dimensionamento (a partir do produto):
  Tampo      → produto + 116 mm em cada dimensão (58 mm cada lado)
  Base       → produto +  80 mm em cada dimensão (40 mm cada lado)
  Lat. Menor → largura = largura da base  | altura = produto_A + 98 mm
  Lat. Maior → largura = comprimento do tampo | altura = produto_A + 98 mm

Furação de marcação (ø 2 mm, prof. 5 mm):
  Tampo      → todos os 4 lados
  Lat. Menor → lado inferior apenas
  Lat. Maior → lado inferior + lados laterais (esq. e dir.)
  Base       → sem furação

Pegadores (Lat. Maior apenas):
  2 recortes oblongos 120 × 50 mm, centro a 150 mm do topo
"""

import os
import math
import zipfile
from typing import List, Tuple, Optional

try:
    import ezdxf
except ImportError:
    print("ERRO: Execute:  pip install ezdxf")
    raise SystemExit(1)


# ── Constantes padrão ──────────────────────────────────────────
ESPESSURA_PADRAO_MM    = 18.0
DENSIDADE_PADRAO       = 700.0

# Furação de marcação
DIAMETRO_FURO_MM       = 5.0
PROF_FURO_MM           = 5.0     # profundidade (referência técnica no DXF)
MARGEM_FURO_MM         = 9.0
ESP_MAX_FUROS_MM       = 80.0    # espaçamento máximo entre furos

# Pegadores
PEGADOR_LARGURA_MM     = 120.0
PEGADOR_ALTURA_MM      = 50.0
PEGADOR_RAIO_CANTO_MM  = 12.0
PEGADOR_DIST_TOPO_MM   = 150.0   # distância do centro do pegador ao topo
PEGADOR_MIN_ALTURA_MM  = 200.0   # altura mínima da peça para inserir pegador


# ── Dimensionamento a partir do produto ────────────────────────

def calcular_dimensoes_chapas(
    produto_c_mm: float,
    produto_l_mm: float,
    produto_a_mm: float,
    espessura_mm: float = ESPESSURA_PADRAO_MM,
) -> dict:
    """
    Calcula as dimensões de todas as chapas a partir das dimensões do produto.

    Padrão Caixaria MDF Exportação:
      Tampo    : C+116 × L+116 × 18
      Base     : C+80  × L+80  × 18
      Lat Menor: largura = base_L | altura = produto_A + 98
      Lat Maior: largura = tampo_C | altura = produto_A + 98

    Returns:
        dict com chaves 'tampo', 'base', 'lat_menor', 'lat_maior'
        cada valor é (largura_mm, altura_mm)
    """
    tampo_c = produto_c_mm + 116
    tampo_l = produto_l_mm + 116
    base_c  = produto_c_mm + 80
    base_l  = produto_l_mm + 80
    alt_lat = produto_a_mm + 98

    return {
        "tampo"    : (tampo_c, tampo_l),
        "base"     : (base_c,  base_l),
        "lat_menor": (base_l,  alt_lat),   # largura = base_l
        "lat_maior": (tampo_c, alt_lat),   # largura = tampo_c (sempre o comprimento do tampo)
    }


# ── Cálculo de peso ────────────────────────────────────────────

def calcular_peso_chapas(
    chapas: dict,
    espessura_mm    : float = ESPESSURA_PADRAO_MM,
    densidade_kg_m3 : float = DENSIDADE_PADRAO,
) -> dict:
    """
    Calcula o peso de cada chapa e o peso total.

    Args:
        chapas: dict no formato de calcular_dimensoes_chapas()
    Returns:
        dict com 'detalhes' e 'peso_total_kg'
    """
    e = espessura_mm / 1000.0
    d = densidade_kg_m3

    mapa = {
        "Tampo"     : (chapas["tampo"],     1),
        "Base"      : (chapas["base"],      1),
        "Lat. Menor": (chapas["lat_menor"], 2),
        "Lat. Maior": (chapas["lat_maior"], 2),
    }

    detalhes = {}
    total = 0.0

    for nome, ((larg, alt), qtd) in mapa.items():
        area  = (larg / 1000.0) * (alt / 1000.0)
        peso  = area * e * d * qtd
        total += peso
        detalhes[nome] = {
            "largura_mm"  : larg,
            "altura_mm"   : alt,
            "quantidade"  : qtd,
            "area_m2"     : area,
            "peso_kg"     : peso,
        }

    return {"detalhes": detalhes, "peso_total_kg": total}


def calcular_peso_produto(
    produto_c_mm    : float,
    produto_l_mm    : float,
    produto_a_mm    : float,
    espessura_mm    : float = ESPESSURA_PADRAO_MM,
    densidade_kg_m3 : float = DENSIDADE_PADRAO,
) -> dict:
    """Atalho: calcula peso direto das dimensões do produto."""
    chapas = calcular_dimensoes_chapas(produto_c_mm, produto_l_mm, produto_a_mm, espessura_mm)
    return calcular_peso_chapas(chapas, espessura_mm, densidade_kg_m3)


# ── Geometrias DXF ─────────────────────────────────────────────

def _furos_na_linha(inicio: float, fim: float,
                    margem: float, esp_max: float) -> List[float]:
    """Retorna posições de furos ao longo de um segmento."""
    comprimento = fim - inicio
    espaco      = comprimento - 2 * margem

    if espaco <= 0:
        return [inicio + comprimento / 2.0]

    n = max(2, int(espaco / esp_max) + 2)
    passo = espaco / (n - 1)
    return [round(inicio + margem + i * passo, 3) for i in range(n)]


def calcular_posicoes_furos(
    largura_mm : float,
    altura_mm  : float,
    bordas     : str   = "todas",   # "todas" | "inferior" | "inferior_laterais"
    margem_mm  : float = MARGEM_FURO_MM,
    esp_max_mm : float = ESP_MAX_FUROS_MM,
) -> List[Tuple[float, float]]:
    """
    Calcula posições dos furos de marcação conforme o tipo de chapa.

    bordas:
        "todas"             → 4 lados (tampo)
        "inferior"          → só borda inferior (lat. menor)
        "inferior_laterais" → inferior + esq./dir. (lat. maior)
    """
    furos: set = set()

    if bordas in ("todas", "inferior", "inferior_laterais"):
        # Borda inferior
        for x in _furos_na_linha(0, largura_mm, margem_mm, esp_max_mm):
            furos.add((x, margem_mm))

    if bordas == "todas":
        # Borda superior
        for x in _furos_na_linha(0, largura_mm, margem_mm, esp_max_mm):
            furos.add((x, round(altura_mm - margem_mm, 3)))

    if bordas in ("todas", "inferior_laterais"):
        # Bordas esquerda e direita
        for y in _furos_na_linha(0, altura_mm, margem_mm, esp_max_mm):
            furos.add((margem_mm,                          round(y, 3)))
            furos.add((round(largura_mm - margem_mm, 3),   round(y, 3)))

    return sorted(furos)


def adicionar_contorno(msp, largura_mm: float, altura_mm: float,
                       layer: str = "CONTORNO") -> None:
    """Retângulo externo da chapa."""
    msp.add_lwpolyline(
        [(0, 0), (largura_mm, 0), (largura_mm, altura_mm), (0, altura_mm)],
        close=True,
        dxfattribs={"layer": layer, "lineweight": 50},
    )


def adicionar_furos(msp, furos: List[Tuple[float, float]],
                    diametro_mm: float = DIAMETRO_FURO_MM,
                    layer: str = "FUROS") -> None:
    """Círculos de furação de marcação."""
    r = diametro_mm / 2.0
    for (x, y) in furos:
        msp.add_circle((x, y), r, dxfattribs={"layer": layer})


def _oblong(msp, cx: float, cy: float,
            largura: float, altura: float, raio: float,
            layer: str) -> None:
    """Desenha um único recorte oblongo (retângulo com cantos arredondados)."""
    r  = min(raio, largura / 2.0, altura / 2.0)
    x0 = cx - largura / 2.0
    x1 = cx + largura / 2.0
    y0 = cy - altura  / 2.0
    y1 = cy + altura  / 2.0
    a  = {"layer": layer, "lineweight": 35}

    msp.add_line((x0 + r, y0), (x1 - r, y0), dxfattribs=a)
    msp.add_arc( (x1 - r, y0 + r), r, 270, 0,   dxfattribs=a)
    msp.add_line((x1, y0 + r), (x1, y1 - r),    dxfattribs=a)
    msp.add_arc( (x1 - r, y1 - r), r, 0, 90,    dxfattribs=a)
    msp.add_line((x1 - r, y1), (x0 + r, y1),    dxfattribs=a)
    msp.add_arc( (x0 + r, y1 - r), r, 90, 180,  dxfattribs=a)
    msp.add_line((x0, y1 - r), (x0, y0 + r),    dxfattribs=a)
    msp.add_arc( (x0 + r, y0 + r), r, 180, 270, dxfattribs=a)


def adicionar_pegadores(
    msp,
    largura_mm     : float,
    altura_mm      : float,
    peg_larg       : float = PEGADOR_LARGURA_MM,
    peg_alt        : float = PEGADOR_ALTURA_MM,
    raio_canto     : float = PEGADOR_RAIO_CANTO_MM,
    dist_topo      : float = PEGADOR_DIST_TOPO_MM,
    layer          : str   = "PEGADORES",
) -> None:
    """
    Insere 2 recortes oblongos na Lat. Maior.

    Posicionamento:
      - cy = altura - dist_topo  (centro a 150 mm do topo)
      - cx1 = largura / 4
      - cx2 = 3 * largura / 4
    """
    if altura_mm < PEGADOR_MIN_ALTURA_MM:
        return  # Peça muito baixa para pegador

    cy  = altura_mm - dist_topo
    if cy - peg_alt / 2.0 < 5:
        cy = peg_alt / 2.0 + 5   # Ajuste de segurança

    cx1 = largura_mm / 4.0
    cx2 = 3.0 * largura_mm / 4.0

    # Garantir que os oblongos cabem horizontalmente
    margem_h = peg_larg / 2.0 + 10
    if cx1 < margem_h:
        cx1 = margem_h
    if cx2 > largura_mm - margem_h:
        cx2 = largura_mm - margem_h

    _oblong(msp, cx1, cy, peg_larg, peg_alt, raio_canto, layer)
    _oblong(msp, cx2, cy, peg_larg, peg_alt, raio_canto, layer)


def adicionar_anotacao(msp, nome: str, largura_mm: float,
                       altura_mm: float, espessura_mm: float) -> None:
    """Texto informativo acima da peça (camada INFO)."""
    msp.add_text(
        f"{nome}  |  {largura_mm:.0f} × {altura_mm:.0f} mm  |  e={espessura_mm:.0f} mm",
        dxfattribs={
            "layer" : "INFO",
            "height": 8.0,
            "insert": (0, altura_mm + 12),
        },
    )


def adicionar_nome_produto(
    msp,
    nome_produto: str,
    largura_mm  : float,
    altura_mm   : float,
    layer       : str = "NOME",
) -> None:
    """
    Insere o nome do produto centralizado no meio da chapa.

    O texto é posicionado no centro geométrico da peça,
    alinhado ao centro horizontal e vertical.
    Tamanho da fonte: 1.5% da maior dimensão (mín. 8 mm, máx. 40 mm).
    """
    if not nome_produto or not nome_produto.strip():
        return

    cx = largura_mm / 2.0
    cy = altura_mm  / 2.0

    # Altura do texto proporcional à peça
    altura_txt = max(8.0, min(40.0, max(largura_mm, altura_mm) * 0.015))

    texto = msp.add_text(
        nome_produto.strip().upper(),
        dxfattribs={
            "layer" : layer,
            "height": altura_txt,
            "style" : "Standard",
        },
    )
    texto.set_placement(
        (cx, cy),
        align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER,
    )


# ── Exportação DXF ─────────────────────────────────────────────

def criar_dxf_chapa(
    nome_arquivo : str,
    largura_mm   : float,
    altura_mm    : float,
    tipo_chapa   : str   = "base",  # "tampo" | "base" | "lat_menor" | "lat_maior"
    espessura_mm : float = ESPESSURA_PADRAO_MM,
    diametro_furo: float = DIAMETRO_FURO_MM,
    margem_furo  : float = MARGEM_FURO_MM,
    pasta_saida  : str   = ".",
    nome_produto : str   = "",
) -> str:
    """
    Gera um arquivo DXF de uma chapa com geometrias conforme o tipo.

    tipo_chapa:
        "tampo"     → contorno + furos 4 lados
        "base"      → contorno apenas
        "lat_menor" → contorno + furos inferior
        "lat_maior" → contorno + furos inferior+laterais + 2 pegadores

    Returns:
        Caminho absoluto do .dxf gerado
    """
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 4  # mm

    doc.layers.add("CONTORNO",  color=7)
    doc.layers.add("FUROS",     color=1)
    doc.layers.add("PEGADORES", color=3)
    doc.layers.add("INFO",      color=8)
    doc.layers.add("NOME",      color=2)   # amarelo — nome do produto

    msp = doc.modelspace()

    # Contorno sempre presente
    adicionar_contorno(msp, largura_mm, altura_mm)

    # Furos conforme tipo
    mapa_bordas = {
        "tampo"    : "todas",
        "base"     : None,               # sem furos
        "lat_menor": "inferior",
        "lat_maior": "inferior_laterais",
    }
    bordas = mapa_bordas.get(tipo_chapa)
    if bordas:
        furos = calcular_posicoes_furos(largura_mm, altura_mm, bordas,
                                        margem_furo)
        adicionar_furos(msp, furos, diametro_furo)
    else:
        furos = []

    # Pegadores apenas na Lat. Maior
    if tipo_chapa == "lat_maior":
        adicionar_pegadores(msp, largura_mm, altura_mm)

    adicionar_anotacao(msp, nome_arquivo, largura_mm, altura_mm, espessura_mm)
    adicionar_nome_produto(msp, nome_produto, largura_mm, altura_mm)

    caminho = os.path.join(pasta_saida, f"{nome_arquivo}.dxf")
    doc.saveas(caminho)

    extras = " + 2 pegadores" if tipo_chapa == "lat_maior" else ""
    print(f"  [OK] {nome_arquivo}.dxf  "
          f"({largura_mm:.0f}×{altura_mm:.0f} mm | {len(furos)} furos{extras})")
    return os.path.abspath(caminho)


def gerar_dxfs_produto(
    produto_c_mm : float,
    produto_l_mm : float,
    produto_a_mm : float,
    pasta_saida  : str   = "dxfs_mdf",
    espessura_mm : float = ESPESSURA_PADRAO_MM,
    diametro_furo: float = DIAMETRO_FURO_MM,
    margem_furo  : float = MARGEM_FURO_MM,
    nome_produto : str   = "",
) -> List[str]:
    """
    Gera os 6 DXFs de uma caixa a partir das dimensões do produto.

    Arquivos gerados:
        tampo.dxf
        base.dxf
        lateral_menor_1.dxf / lateral_menor_2.dxf
        lateral_maior_1.dxf / lateral_maior_2.dxf

    Returns:
        Lista dos caminhos absolutos gerados
    """
    os.makedirs(pasta_saida, exist_ok=True)
    chapas = calcular_dimensoes_chapas(produto_c_mm, produto_l_mm, produto_a_mm, espessura_mm)

    print(f"\n{'='*64}")
    print(f"  GERANDO DXFs — produto {produto_c_mm:.0f}×{produto_l_mm:.0f}×{produto_a_mm:.0f} mm")
    print(f"  Pasta: {pasta_saida}/")
    print(f"{'='*64}")

    opts = dict(espessura_mm=espessura_mm, diametro_furo=diametro_furo,
                margem_furo=margem_furo, pasta_saida=pasta_saida,
                nome_produto=nome_produto)
    arquivos: List[str] = []

    lm_l, lm_a = chapas["lat_menor"]
    lM_l, lM_a = chapas["lat_maior"]
    t_l,  t_a  = chapas["tampo"]
    b_l,  b_a  = chapas["base"]

    for i in (1, 2):
        arquivos.append(criar_dxf_chapa(f"lateral_menor_{i}", lm_l, lm_a,
                                         tipo_chapa="lat_menor", **opts))
    for i in (1, 2):
        arquivos.append(criar_dxf_chapa(f"lateral_maior_{i}", lM_l, lM_a,
                                         tipo_chapa="lat_maior", **opts))
    arquivos.append(criar_dxf_chapa("tampo", t_l, t_a, tipo_chapa="tampo", **opts))
    arquivos.append(criar_dxf_chapa("base",  b_l, b_a, tipo_chapa="base",  **opts))

    print(f"{'='*64}")
    print(f"  Total: {len(arquivos)} arquivos gerados")
    return arquivos


def gerar_dxfs_manuais(
    lat_menor_l_mm: float, lat_menor_a_mm: float,
    lat_maior_l_mm: float, lat_maior_a_mm: float,
    tampo_l_mm    : float, tampo_a_mm    : float,
    base_l_mm     : float, base_a_mm     : float,
    pasta_saida   : str   = "dxfs_mdf",
    espessura_mm  : float = ESPESSURA_PADRAO_MM,
    diametro_furo : float = DIAMETRO_FURO_MM,
    margem_furo   : float = MARGEM_FURO_MM,
    nome_produto  : str   = "",
) -> List[str]:
    """Gera os 6 DXFs a partir de dimensões informadas manualmente."""
    os.makedirs(pasta_saida, exist_ok=True)
    opts = dict(espessura_mm=espessura_mm, diametro_furo=diametro_furo,
                margem_furo=margem_furo, pasta_saida=pasta_saida,
                nome_produto=nome_produto)
    arquivos: List[str] = []

    for i in (1, 2):
        arquivos.append(criar_dxf_chapa(f"lateral_menor_{i}",
                                         lat_menor_l_mm, lat_menor_a_mm,
                                         tipo_chapa="lat_menor", **opts))
    for i in (1, 2):
        arquivos.append(criar_dxf_chapa(f"lateral_maior_{i}",
                                         lat_maior_l_mm, lat_maior_a_mm,
                                         tipo_chapa="lat_maior", **opts))
    arquivos.append(criar_dxf_chapa("tampo", tampo_l_mm, tampo_a_mm,
                                     tipo_chapa="tampo", **opts))
    arquivos.append(criar_dxf_chapa("base", base_l_mm, base_a_mm,
                                     tipo_chapa="base", **opts))
    return arquivos


def exportar_zip(arquivos: List[str], nome_zip: str = "chapas_mdf.zip",
                 pasta_saida: str = ".") -> str:
    """Compacta os DXFs em um ZIP."""
    caminho = os.path.join(pasta_saida, nome_zip)
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as zf:
        for arq in arquivos:
            zf.write(arq, arcname=os.path.basename(arq))
    kb = os.path.getsize(caminho) / 1024
    print(f"\n  [ZIP] {nome_zip}  ({len(arquivos)} arquivos | {kb:.1f} KB)")
    return os.path.abspath(caminho)
