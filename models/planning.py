# models/planning.py
import numpy as np
import pandas as pd

def projetar_futuro(df_base, anos_frente, taxa_crescimento_anual=0.03):
    """
    Projeta a curva de carga para horizontes de longo prazo usando
    a formulação de crescimento composto anual de demanda.
    """
    if anos_frente == 0:
        return df_base.copy()
        
    fator_crescimento = (1 + taxa_crescimento_anual) ** anos_frente
    df_futuro = df_base.copy()
    
    # Projeta a carga baseado na taxa vegetativa de 3% ao ano
    df_futuro['carga_mw'] = df_base['carga_mw'] * fator_crescimento
    
    return df_futuro

def simular_stress(df, choque_demanda=0.0):
    """
    Injeta distúrbios estocásticos na demanda horária representando
    ondas bruscas de calor ou comportamento instável de consumo industrial.
    """
    df_stress = df.copy()
    
    if choque_demanda > 0:
        # Distribuição gaussiana com média zero e desvio proporcional ao choque parametrizado
        ruido = np.random.normal(loc=1.0, scale=choque_demanda, size=len(df_stress))
        df_stress['carga_mw'] = df_stress['carga_mw'] * ruido
        
    return df_stress