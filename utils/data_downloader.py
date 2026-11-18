# utils/data_downloader.py
import pandas as pd
import numpy as np
import requests
import os

def download_carga_ons(ano=2024):
    """
    Tenta realizar o download de dados reais de carga horária do ONS.
    Utiliza 2024 como ano base consolidado e estável para modelagem didática.
    """
    print(f"🚀 Tentando baixar dados reais de {ano}...")
    
    # URL do ONS Open Data hospedada na AWS S3
    url = f"https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/curva-carga-ho/CURVA_CARGA_{ano}.csv"
    destino = f"data/raw/carga_{ano}.csv"
    
    try:
        os.makedirs("data/raw", exist_ok=True)
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            with open(destino, 'wb') as f:
                f.write(response.content)
            print(f"✅ Sucesso! Arquivo salvo em: {destino}")
            return destino
        else:
            print(f"⚠️ ONS retornou erro {response.status_code}. Gerando dados simulados.")
            return gerar_dados_simulados(ano)
    except Exception as e:
        print(f"⚠️ Erro de conexão: {e}. Gerando simulados...")
        return gerar_dados_simulados(ano)

def gerar_dados_simulados(ano):
    """
    Simula uma série de demanda horária com comportamento físico e
    aleatório coerente com a realidade brasileira (Senoide diária + Ruído).
    """
    print("🛠️ Gerando dados sintéticos para desenvolvimento...")
    datas = pd.date_range(start=f"{ano}-01-01", end=f"{ano}-01-07 23:00:00", freq='H')
    
    # Modelagem física básica da carga: Base estável + variação diária senoidal + ruído estocástico
    base = 30000
    senoide = 5000 * np.sin(2 * np.pi * datas.hour / 24 - np.pi/2)
    ruido = np.random.normal(0, 500, len(datas))
    carga = base + senoide + ruido
    
    df = pd.DataFrame({
        'din_instante': datas,
        'id_subsistema': 'NE',
        'val_cargaenergiahomwmed': carga
    })
    
    destino = f"data/raw/carga_{ano}_simulada.csv"
    os.makedirs("data/raw", exist_ok=True)
    df.to_csv(destino, index=False, sep=';')
    return destino

def processar_carga(caminho_csv):
    """
    Carrega o arquivo baixado/simulado, trata sua estrutura, unifica
    nomes de colunas para blindagem de código e exporta os dados processados.
    """
    if not caminho_csv: return None
    
    print("🧹 Processando e estruturando os dados...")
    try:
        df = pd.read_csv(caminho_csv, sep=';')
        if 'din_instante' not in df.columns:
             df = pd.read_csv(caminho_csv, sep=',')
    except:
        df = pd.read_csv(caminho_csv, sep=',')

    df['din_instante'] = pd.to_datetime(df['din_instante'])
    
    # Derivando colunas de controle temporal importantes para visualização
    df['data'] = df['din_instante'].dt.date
    df['hora'] = df['din_instante'].dt.hour
    
    destino_clean = "data/processed/carga_limpa.csv"
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(destino_clean, index=False)
    print(f"✨ Pronto! Arquivo processado disponível em: {destino_clean}")
    return df

if __name__ == "__main__":
    arquivo = download_carga_ons(2024)
    processar_carga(arquivo)