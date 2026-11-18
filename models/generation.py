# models/generation.py
import numpy as np
import pandas as pd

def calcular_geracao_solar(hora, p_instalada):
    """
    Simula uma curva de insolação diurna típica senoidal entre 06:00 e 18:00.
    Injeta perdas e limites físicos para maior aproximação da realidade acadêmica.
    """
    if hora < 6 or hora > 18:
        return 0.0
    
    eficiencia = 0.8  # Fator de perdas sistêmicas (temperatura, inversores, etc.)
    angulo = np.pi * (hora - 6) / 12
    geracao = p_instalada * eficiencia * np.sin(angulo)
    
    return max(0, geracao)

def calcular_geracao_eolica(hora, p_instalada):
    """
    Simula o comportamento do vento do Nordeste brasileiro (vento predominantemente
    noturno e com quedas de produção no período central do dia).
    """
    # Curva senoidal invertida com pico nas pontas do dia (madrugada/noite)
    fator_horario = 0.7 + 0.3 * np.cos(2 * np.pi * (hora - 2) / 24)
    
    # Inclusão de ruído estocástico na produção eólica horária
    ruido = np.random.uniform(0.9, 1.1)
    
    return p_instalada * fator_horario * ruido

def aplicar_geracao_ao_df(df, p_solar, p_eolica):
    """
    Aplica as fórmulas físicas ao dataframe de análise e gera a coluna de Carga Líquida.
    """
    df['gen_solar'] = df['hora'].apply(lambda x: calcular_geracao_solar(x, p_solar))
    df['gen_eolica'] = df['hora'].apply(lambda x: calcular_geracao_eolica(x, p_eolica))
    
    # Cálculo crucial: Carga Líquida
    df['carga_liquida'] = df['carga_mw'] - (df['gen_solar'] + df['gen_eolica'])
    df['carga_liquida'] = df['carga_liquida'].clip(lower=0) # Evita valores negativos de carga
    
    return df