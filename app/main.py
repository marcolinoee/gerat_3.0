# app/main.py
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sys

# --- AJUSTE DE AMBIENTE (SYS.PATH) ---
# Força o Python a localizar os pacotes internos independente de onde o script Streamlit foi inicializado
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.generation import aplicar_geracao_ao_df
from models.dispatch import executar_despacho
from models.planning import projetar_futuro, simular_stress

# --- INICIALIZAÇÃO E DESIGN DA INTERFACE ---
st.set_page_config(page_title="Novo GERAT - 2026", layout="wide")

def carregar_dados():
    path = "data/processed/carga_limpa.csv"
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    # Garante compatibilidade caso ocorram variações no layout de tabelas de ONS anteriores
    mapeamento = {
        'val_cargaenergiahomwmed': 'carga_mw',
        'val_cargaenergiareteada': 'carga_mw',
        'val_carga_mw': 'carga_mw'
    }
    df = df.rename(columns=mapeamento)
    df['din_instante'] = pd.to_datetime(df['din_instante'])
    return df

def calcular_cmo(row, termicas):
    """
    Define o Custo Marginal de Operação.
    O CMO corresponde ao valor de CVU da última fonte termoelétrica necessária.
    """
    cmo = 0
    termicas_ord = sorted(termicas, key=lambda x: x['cvu'])
    for t in termicas_ord:
        if row.get(f"gen_termica_{t['nome']}", 0) > 0.01:
            cmo = t['cvu']
    return cmo

# --- CABEÇALHO ---
st.title("⚡ Novo GERAT: Sistema Educacional de Previsão e Despacho")
st.markdown("Plataforma de modelagem didática para transição energética e planejamento elétrico de longo prazo.")
st.markdown("---")

df_carga = carregar_dados()

if df_carga is not None:
    # --- BARRA LATERAL (SIDEBAR): CONTROLADORES OPERACIONAIS ---
    st.sidebar.header("🛠️ Operação do Sistema")
    
    datas_disponiveis = df_carga['din_instante'].dt.date.unique()
    data_selecionada = st.sidebar.selectbox("Dia de Análise Base", datas_disponiveis)
    
    st.sidebar.subheader("Capacidade Atual (MW)")
    cap_solar = st.sidebar.slider("Solar Fotovoltaica", 0, 30000, 8000)
    cap_eolica = st.sidebar.slider("Eólica", 0, 40000, 15000)
    cap_hidro = st.sidebar.slider("Disponibilidade Hidro Nominal", 0, 60000, 30000)
    
    # --- BARRA LATERAL: CONTROLADORES DE EXPANSÃO ---
    st.sidebar.divider()
    st.sidebar.header("🔮 Planejamento de Longo Prazo")
    
    anos_frente = st.sidebar.slider("Projetar Demanda (Anos à frente)", 0, 30, 0, 
                                    help="Simula o crescimento anual médio de 3% de consumo vegetativo.")
    
    st.sidebar.subheader("⚠️ Cenários de Estresse")
    seca_extrema = st.sidebar.checkbox("Simular Seca Extrema (El Niño)")
    choque_demanda = st.sidebar.checkbox("Choque Estocástico de Demanda")

    # Matriz Térmica com custos escalonados
    termicas = [
        {'nome': 'Nuclear', 'cap': 2000, 'cvu': 45},
        {'nome': 'Gás Natural', 'cap': 10000, 'cvu': 280},
        {'nome': 'Biomassa', 'cap': 4000, 'cvu': 450},
        {'nome': 'Óleo Diesel', 'cap': 3000, 'cvu': 950}
    ]

    # --- EXECUÇÃO COMPLETA DO MOTOR DE CÁLCULO ---
    df_dia = df_carga[df_carga['din_instante'].dt.date == data_selecionada].sort_values('hora').copy()
    
    # 1. Aplica o Crescimento Vegetativo (Projeções de Longo Prazo)
    df_dia = projetar_futuro(df_dia, anos_frente)
    
    # 2. Aplica Incerteza Estocástica de Demanda
    if choque_demanda:
        df_dia = simular_stress(df_dia, choque_demanda=0.08) # 8% de flutuação de ruído
        
    # 3. Aplica Escassez Hídrica (Corta em 70% a vazão gerada pelas usinas hidrelétricas)
    cap_hidro_real = cap_hidro * 0.3 if seca_extrema else cap_hidro
    
    # 4. Processamento de Curva de Geração Solar/Eólica e Carga Líquida
    df_dia = aplicar_geracao_ao_df(df_dia, cap_solar, cap_eolica)
    
    # 5. Processamento do Despacho por Ordem de Mérito
    df_dia = executar_despacho(df_dia, cap_hidro_real, termicas)
    
    # 6. Cálculo do Custo Marginal Operacional
    df_dia['cmo'] = df_dia.apply(lambda r: calcular_cmo(r, termicas), axis=1)

    # --- RENDERIZAÇÃO DA INTERFACE GRÁFICA ---
    
    # Painel de Indicadores em Linha
    c1, c2, c3, c4 = st.columns(4)
    pico = df_dia['carga_mw'].max()
    gen_total_renov = (df_dia['gen_solar'].sum() + df_dia['gen_eolica'].sum())
    participacao = (gen_total_renov / df_dia['carga_mw'].sum()) * 100
    
    # Cálculo para validação de Déficit de Abastecimento (Colapso)
    total_termica = sum(df_dia[f"gen_termica_{t['nome']}"].sum() for t in termicas)
    deficit_energia = df_dia['carga_liquida'].sum() - df_dia['gen_hidro'].sum() - total_termica
    
    c1.metric("Pico de Demanda Projetada", f"{pico:,.0f} MW", f"+{anos_frente} Anos" if anos_frente>0 else None)
    c2.metric("Penetração Renovável", f"{participacao:.1f} %")
    c3.metric("CMO Médio Diário", f"R$ {df_dia['cmo'].mean():.2f}")
    
    if deficit_energia > 1: # Flag do temido "Apagão"
        c4.error(f"DÉFICIT! Faltou: {deficit_energia:,.0f} MWh")
    else:
        c4.metric("Custo Térmico Diário", f"R$ {(df_dia['cmo'] * df_dia['carga_mw']).sum():,.0f}")

    # Gráfico 1: Despacho e Mix Energético Horário
    st.subheader("Balanço Energético Horário")
    colunas_mix = ['gen_solar', 'gen_eolica', 'gen_hidro', 
                   'gen_termica_Nuclear', 'gen_termica_Gás Natural', 
                   'gen_termica_Biomassa', 'gen_termica_Óleo Diesel']
    
    fig_mix = px.area(df_dia, x='hora', y=colunas_mix,
                     labels={'value': 'Geração (MW)', 'variable': 'Fonte de Geração'},
                     color_discrete_map={
                         'gen_solar': '#FFD700', 'gen_eolica': '#00FA9A', 'gen_hidro': '#1E90FF',
                         'gen_termica_Nuclear': '#9370DB', 'gen_termica_Gás Natural': '#FFA07A',
                         'gen_termica_Biomassa': '#8B4513', 'gen_termica_Óleo Diesel': '#2F4F4F'
                     })
    # Desenho da linha preta representando a demanda que as usinas devem buscar em tempo real
    fig_mix.add_scatter(x=df_dia['hora'], y=df_dia['carga_mw'], name='Demanda Projetada', 
                       line=dict(color='black', dash='dash', width=2))
    st.plotly_chart(fig_mix, use_container_width=True)

    # Gráfico 2: CMO Horário em formato Degrau
    st.subheader("Sinal de Preço: Custo Marginal de Operação (CMO)")
    fig_cmo = px.line(df_dia, x='hora', y='cmo', 
                      title="CMO Horário (R$/MWh)",
                      labels={'cmo': 'R$/MWh', 'hora': 'Hora'})
    fig_cmo.update_traces(line_color='#FF3860', line_shape='hv') # hv = escadinha (técnicamente correto para CMO)
    st.plotly_chart(fig_cmo, use_container_width=True)

    # Tabela com as informações numéricas detalhadas
    with st.expander("🔍 Ver Matriz de Dados Completa"):
        st.dataframe(df_dia)

else:
    st.error("🚨 Arquivo de dados de carga limpa não localizado.")
    st.info("⚠️ Execute primeiro no console: 'python utils/data_downloader.py' para sincronizar os dados.")

st.divider()
st.caption("Novo GERAT - Manual de Especificação Técnica Integrada (2026)")