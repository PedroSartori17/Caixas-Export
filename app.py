"""
Sistema de Caixas MDF — Interface Web (Streamlit)
Execute com: python3 -m streamlit run app.py
"""

import io
import os
import zipfile
import tempfile
import streamlit as st

from mdf_box_system import (
    calcular_dimensoes_chapas,
    calcular_peso_chapas,
    gerar_dxfs_produto,
    gerar_dxfs_manuais,
    ESPESSURA_PADRAO_MM,
    DENSIDADE_PADRAO,
    DIAMETRO_FURO_MM,
    MARGEM_FURO_MM,
)

# ── Página ──────────────────────────────────────────────────────
st.set_page_config(page_title="Caixas MDF", page_icon="📦", layout="centered")

st.markdown("""
<style>
  .block-container { padding-top: 2rem; }
  .peso-box {
    background: #1a1a2e; border-radius: 14px;
    padding: 20px 28px; margin: 16px 0;
  }
  .peso-label { color: #aaa; font-size: 14px; margin: 0; }
  .peso-valor { color: #fff; font-size: 38px; font-weight: 700; margin: 4px 0; }
  .dim-card {
    background: #0f3460; border-radius: 10px;
    padding: 12px 16px; margin: 6px 0;
  }
  .dim-nome  { color: #e0e0e0; font-size: 13px; font-weight: 600; }
  .dim-valor { color: #a8d8ea; font-size: 15px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

st.title("📦 Calculadora de Caixas MDF")
st.caption("Padrão de Caixaria MDF para Exportação — calcula chapas, peso e gera DXFs.")
st.divider()


# ── Helpers ─────────────────────────────────────────────────────
def fmt(v: float) -> str:
    """Formata número com vírgula decimal (padrão BR)."""
    return f"{v:.3f}".replace(".", ",")


def gerar_zip_buffer(arquivos: list) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arq in arquivos:
            zf.write(arq, arcname=os.path.basename(arq))
    buf.seek(0)
    return buf


def mostrar_peso(resultado: dict, label: str = "Peso total da caixa") -> None:
    total = resultado["peso_total_kg"]
    st.markdown(f"""
    <div class="peso-box">
      <p class="peso-label">{label}</p>
      <p class="peso-valor">{fmt(total)} kg</p>
    </div>""", unsafe_allow_html=True)

    cols = st.columns([3, 2, 1, 2])
    cols[0].markdown("**Chapa**")
    cols[1].markdown("**Dimensão (mm)**")
    cols[2].markdown("**Qtd**")
    cols[3].markdown("**Peso (kg)**")
    for nome, d in resultado["detalhes"].items():
        c = st.columns([3, 2, 1, 2])
        c[0].write(nome)
        c[1].write(f"{d['largura_mm']:.0f} × {d['altura_mm']:.0f}")
        c[2].write(f"×{d['quantidade']}")
        c[3].write(f"**{fmt(d['peso_kg'])}**")


def mostrar_dimensoes(chapas: dict) -> None:
    nomes = {
        "tampo"    : "Tampo",
        "base"     : "Base",
        "lat_menor": "Lat. Menor (×2)",
        "lat_maior": "Lat. Maior (×2)",
    }
    cols = st.columns(2)
    for i, (k, (larg, alt)) in enumerate(chapas.items()):
        with cols[i % 2]:
            st.markdown(f"""
            <div class="dim-card">
              <div class="dim-nome">{nomes[k]}</div>
              <div class="dim-valor">{larg:.0f} × {alt:.0f} mm</div>
            </div>""", unsafe_allow_html=True)


def botao_dxf(key: str, fn_gerar, **kwargs) -> None:
    """Renderiza botão de geração de DXF + botão de download."""
    if st.button("🖨️ Gerar e baixar ZIP com todos os DXFs",
                 type="primary", use_container_width=True, key=f"btn_{key}"):
        with st.spinner("Gerando arquivos DXF..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                arquivos = fn_gerar(pasta_saida=tmpdir, **kwargs)
                buf = gerar_zip_buffer(arquivos)
        st.session_state[f"zip_{key}"] = buf
        st.session_state[f"n_{key}"]   = len(arquivos)

    if f"zip_{key}" in st.session_state:
        n = st.session_state[f"n_{key}"]
        st.success(f"✅ {n} arquivos DXF gerados!")
        st.download_button(
            label="⬇️ Baixar chapas_mdf.zip",
            data=st.session_state[f"zip_{key}"],
            file_name="chapas_mdf.zip",
            mime="application/zip",
            use_container_width=True,
            key=f"dl_{key}",
        )


# ── Abas ────────────────────────────────────────────────────────
aba_produto, aba_manual = st.tabs([
    "📦 Por Produto (automático)",
    "🔧 Chapas Manuais",
])


# ════════════════════════════════════════════════════════════════
# ABA 1 — POR PRODUTO
# ════════════════════════════════════════════════════════════════
with aba_produto:
    nome1 = st.text_input(
        "🏷️ Nome do produto",
        placeholder="Ex: MESA DE JANTAR 6 LUGARES",
        key="nome1",
    )

    st.subheader("Dimensões do produto")
    st.caption("Informe as medidas do item que será embalado.")

    col1, col2, col3 = st.columns(3)
    with col1:
        pC = st.number_input("Comprimento (mm)", min_value=1.0, value=1200.0, step=10.0, key="pC")
    with col2:
        pL = st.number_input("Largura (mm)",     min_value=1.0, value=670.0,  step=10.0, key="pL")
    with col3:
        pA = st.number_input("Altura (mm)",      min_value=1.0, value=250.0,  step=10.0, key="pA")

    col4, col5 = st.columns(2)
    with col4:
        esp1 = st.number_input("Espessura MDF (mm)", min_value=1.0,
                               value=ESPESSURA_PADRAO_MM, step=1.0, key="esp1")
    with col5:
        den1 = st.number_input("Densidade (kg/m³)", min_value=100.0,
                               value=DENSIDADE_PADRAO, step=10.0, key="den1")

    with st.expander("⚙️ Furação"):
        c6, c7 = st.columns(2)
        diam1 = c6.number_input("Diâmetro (mm)", min_value=0.5, value=DIAMETRO_FURO_MM,
                                step=0.5, key="diam1")
        marg1 = c7.number_input("Margem borda (mm)", min_value=1.0, value=MARGEM_FURO_MM,
                                step=1.0, key="marg1")

    # Cálculo em tempo real
    chapas1  = calcular_dimensoes_chapas(pC, pL, pA, esp1)
    resultado1 = calcular_peso_chapas(chapas1, esp1, den1)

    st.divider()
    st.subheader("Chapas calculadas")
    mostrar_dimensoes(chapas1)

    st.subheader("Peso total")
    mostrar_peso(resultado1, f"Produto {pC:.0f}×{pL:.0f}×{pA:.0f} mm")

    st.divider()
    st.subheader("📁 Gerar DXFs")
    botao_dxf(
        key="prod",
        fn_gerar=gerar_dxfs_produto,
        produto_c_mm=pC, produto_l_mm=pL, produto_a_mm=pA,
        espessura_mm=esp1, diametro_furo=diam1, margem_furo=marg1,
        nome_produto=nome1,
    )


# ════════════════════════════════════════════════════════════════
# ABA 2 — CHAPAS MANUAIS
# ════════════════════════════════════════════════════════════════
with aba_manual:
    nome2 = st.text_input(
        "🏷️ Nome do produto",
        placeholder="Ex: SOFÁ 3 LUGARES",
        key="nome2",
    )

    st.subheader("Dimensões de cada chapa")
    st.caption("Informe as medidas já calculadas de cada peça.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Lat. Menor** — Esq./Dir. (×2)")
        lm_l = st.number_input("Largura (mm)", min_value=1.0, value=730.0, step=10.0, key="lm_l")
        lm_a = st.number_input("Altura (mm)",  min_value=1.0, value=298.0, step=10.0, key="lm_a")
    with col2:
        st.markdown("**Lat. Maior** — Frente/Fundo (×2)")
        lM_l = st.number_input("Largura (mm)", min_value=1.0, value=1296.0, step=10.0, key="lM_l")
        lM_a = st.number_input("Altura (mm)",  min_value=1.0, value=298.0,  step=10.0, key="lM_a")

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**Tampo**")
        t_l = st.number_input("Largura (mm)",     min_value=1.0, value=1296.0, step=10.0, key="t_l")
        t_a = st.number_input("Comprimento (mm)", min_value=1.0, value=766.0,  step=10.0, key="t_a")
    with col4:
        st.markdown("**Base**")
        mesma = st.checkbox("Mesmas dim. do tampo", value=False, key="mesma")
        if mesma:
            b_l, b_a = t_l, t_a
            st.info(f"{t_l:.0f} × {t_a:.0f} mm")
        else:
            b_l = st.number_input("Largura (mm)",     min_value=1.0, value=1260.0, step=10.0, key="b_l")
            b_a = st.number_input("Comprimento (mm)", min_value=1.0, value=730.0,  step=10.0, key="b_a")

    col5, col6 = st.columns(2)
    with col5:
        esp2 = st.number_input("Espessura MDF (mm)", min_value=1.0,
                               value=ESPESSURA_PADRAO_MM, step=1.0, key="esp2")
    with col6:
        den2 = st.number_input("Densidade (kg/m³)", min_value=100.0,
                               value=DENSIDADE_PADRAO, step=10.0, key="den2")

    with st.expander("⚙️ Furação"):
        c7, c8 = st.columns(2)
        diam2 = c7.number_input("Diâmetro (mm)", min_value=0.5, value=DIAMETRO_FURO_MM,
                                step=0.5, key="diam2")
        marg2 = c8.number_input("Margem borda (mm)", min_value=1.0, value=MARGEM_FURO_MM,
                                step=1.0, key="marg2")

    # Peso em tempo real
    e2 = esp2 / 1000.0
    chapas_man = {
        "tampo"    : (t_l,  t_a),
        "base"     : (b_l,  b_a),
        "lat_menor": (lm_l, lm_a),
        "lat_maior": (lM_l, lM_a),
    }
    resultado2 = calcular_peso_chapas(chapas_man, esp2, den2)

    st.divider()
    st.subheader("Peso total")
    mostrar_peso(resultado2)

    st.divider()
    st.subheader("📁 Gerar DXFs")
    botao_dxf(
        key="man",
        fn_gerar=lambda pasta_saida, **kw: gerar_dxfs_manuais(pasta_saida=pasta_saida, **kw),
        lat_menor_l_mm=lm_l, lat_menor_a_mm=lm_a,
        lat_maior_l_mm=lM_l, lat_maior_a_mm=lM_a,
        tampo_l_mm=t_l, tampo_a_mm=t_a,
        base_l_mm=b_l,  base_a_mm=b_a,
        espessura_mm=esp2, diametro_furo=diam2, margem_furo=marg2,
        nome_produto=nome2,
    )


st.divider()
st.caption("MDF padrão: e=18 mm · ρ=700 kg/m³ · furos ø5 mm a 9 mm da borda · pegadores 120×50 mm")
