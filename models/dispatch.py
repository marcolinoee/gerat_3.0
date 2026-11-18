# models/dispatch.py
import pandas as pd

def executar_despacho(df, disponibilidade_hidro, lista_termicas):
    """
    Equilibra a carga líquida despachando a matriz hidrelétrica
    e complementando com o parque térmico pela ordem crescente de CVU.
    """
    # 1. Alocação de Geração Hidroelétrica (limitada pela vazão/estoque do dia)
    df['gen_hidro'] = df['carga_liquida'].apply(lambda x: min(x, disponibilidade_hidro))
    
    # Sobra que as usinas termoelétricas deverão cobrir
    df['sobra_termica'] = df['carga_liquida'] - df['gen_hidro']
    
    # 2. Despacho Térmico Ordenado
    termicas_ordenadas = sorted(lista_termicas, key=lambda x: x['cvu'])
    
    for termica in termicas_ordenadas:
        nome_col = f"gen_termica_{termica['nome']}"
        capacidade = termica['cap']
        
        df[nome_col] = 0.0
        for i, row in df.iterrows():
            geracao = min(row['sobra_termica'], capacidade)
            df.at[i, nome_col] = geracao
            # Deduz o saldo do que sobrou para as térmicas subsequentes
            df.at[i, 'sobra_termica'] -= geracao
            
    return df