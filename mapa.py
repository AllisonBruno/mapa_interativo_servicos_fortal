import pandas as pd
import geopandas as gpd
import folium
from folium import LayerControl, FeatureGroup 
import os
import unidecode
from shapely.geometry import Point 
from shapely import wkt 
from folium.features import GeoJsonTooltip
from branca.colormap import StepColormap, LinearColormap 
import warnings

# Ignorar warnings
warnings.filterwarnings('ignore', 'The behavior of DataFrame concatenation with non-unique indices is deprecated', UserWarning) 
warnings.filterwarnings('ignore', 'Geometry is in a geographic CRS', UserWarning) 
warnings.filterwarnings('ignore', 'The behavior of DataFrame concatenation with non-unique indices is deprecated', FutureWarning) 


# --- CONFIGURAÇÃO DE ARQUIVOS ---
ARQUIVO_GPKG = "CE_setores_CD2022.gpkg"
ARQUIVO_DADOS = "fortaleza_dados_analise_SERVICOS_COMPLETO.xlsx"
# Nome do arquivo foi mantido, mas o leitor será ajustado para excel
ARQUIVO_PRECO_M2 = "Fortaleza_Preco_Metro_Quadrado.xlsx" 
ARQUIVO_MAPA_SAIDA = "mapa_caracterizacao_servicos_FINAL_v29_M2_OK.html" 
CODIGO_FORTALEZA_STR = '2304400' 
ARQUIVO_CICLOFAIXA_LAZER = "Ciclofaixa_de_Lazer.csv" 
ARQUIVO_DEMOGRAFIA = "demografia.xlsx" 


# --- FUNÇÕES AUXILIARES ---

def normalizar_nome(nome):
    """Remove acentos, espaços extras e converte para minúsculas."""
    if pd.isna(nome) or nome is None: return None
    return unidecode.unidecode(str(nome)).lower().strip().replace('-', ' ')

# ===============================================================
# FUNÇÃO 1: CRIAÇÃO DE CAMADA COROPLÉTICA (V27)
# ===============================================================
def criar_camada_coropletica(m, gdf, coluna, nome_camada, cmap='RdYlGn', is_default_open=False, estilo_transparente_zero=False):
    """Cria uma camada GeoJson coroplética com escala de cores progressiva (Sem Legenda)."""
    
    valid_data = gdf[coluna].dropna()
    valid_data = valid_data[valid_data >= 0] 
    
    # Lógica para dados nulos ou zero
    if valid_data.empty or valid_data.max() == 0.0:
        def style_function_zero(feature):
            return {'fillColor': '#FFFFFF', 'fillOpacity': 0.0, 'color': '#333333', 'weight': 0.5}

        geojson_layer = folium.GeoJson(gdf, name=nome_camada, style_function=style_function_zero, show=is_default_open).add_to(m)
        tooltip_fields = ['NOME_BAIRRO', coluna]
        geojson_layer.add_child(GeoJsonTooltip(fields=tooltip_fields, aliases=['Bairro:', f'{nome_camada}:'], localize=True, style=("background-color: white; color: #333333; font-family: sans-serif; font-size: 14px; padding: 10px;"), sticky=True))
        if valid_data.max() == 0.0:
            print(f"Aviso: Todos os valores para '{nome_camada}' são zero. Camada criada com cor única ou transparente.")
        return

    min_val = valid_data.min()
    max_val = valid_data.max() 
    
    # --- DEFINIÇÃO DOS BINS E CORES ---
    if cmap == 'YlGn': 
        
        if ('%' in coluna) or (max_val <= 100 and min_val >= 0):
            bins = list(valid_data.quantile([0.25, 0.50])) 
            breakpoints = [0.0, bins[0], bins[1], 80.0, 90.0, 95.0, 100.0]
            bins = sorted(list(set([b for b in breakpoints if b <= max_val and b >= 0.0])))
            
            if len(bins) < 3:
                 bins = list(valid_data.quantile([0, 0.25, 0.50, 0.75, 1.0]))
                 bins[0] = 0.0

            color_list_full = ['#FFFFFF', '#e0f3db', '#b3cde3', '#8c96c6', '#8856a7', '#810f7c', '#6a0a66'] 
            color_list = color_list_full[:len(bins) - 1] 
            
        else: # Para métricas não percentuais
            bins = list(valid_data.quantile([0, 0.25, 0.50, 0.75, 1.0]))
            bins[0] = 0.0 
            color_list = ['#FFFFFF', '#b3cde3', '#8c96c6', '#8856a7', '#810f7c'] 
            
        if coluna == 'KM_CICLOVIA':
            bins = list(valid_data.quantile([0, 0.25, 0.50, 0.75, 1.0]))
            bins[0] = 0.0 
            bins = sorted(list(set(bins)))
            if bins[1] < 0.01: bins = bins[1:]
            bins.insert(0, 0.0)
            bins = sorted(list(set(bins)))

            color_list_full = ['#FFFFFF', '#e0f3db', '#b3cde3', '#8c96c6', '#755bb2', '#4a1486', '#37004d'] 
            color_list = color_list_full[:len(bins) - 1] 

    elif cmap == 'YlOrRd': 
        # Para Carências/Sem Acesso (maior % = mais escuro/vermelho)
        q_50 = valid_data.quantile(0.50)
        q_75 = valid_data.quantile(0.75)
        color_list_full = ['#FFFFFF', '#fecc5c', '#fd8d3c', '#e31a1c', '#800026'] 
        breakpoints = [0.0, 1.0, q_50, q_75, 100.0] 
        bins = sorted(list(set([b for b in breakpoints if b <= max_val])))
        if 0.0 not in bins: bins.insert(0, 0.0)
        bins = sorted(list(set(bins)))
        
        if len(bins) < 2:
            if max_val > 0.01:
                bins = [0.0, max_val] 
            else:
                bins = [0.0, 0.01] 
                
        cores_necessarias = len(bins) - 1
        color_list = color_list_full[:cores_necessarias] 
        if not color_list:
            color_list = ['#800026'] * cores_necessarias 
        
    elif cmap == 'YlOrBr': # CMAP para preço/renda (Amarelo claro -> Marrom escuro)
        bins = list(valid_data.quantile([0, 0.25, 0.50, 0.75, 1.0]))
        bins[0] = 0.0 
        color_list = ['#FFFFFF', '#fee5d9', '#fdd49e', '#fdbb84', '#fc8d59', '#ef6548', '#d7301f', '#990000']
        color_list = color_list[len(color_list) - len(bins) + 1:] 

    else: 
        # Default (RdYlGn - para ICS)
        bins = list(valid_data.quantile([0, 0.2, 0.4, 0.6, 0.8, 1.0]))
        bins[0] = 0.0 
        color_list = ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee090', '#ffffbf', '#e0f3f8', '#abd9e9', '#74add1', '#4575b4', '#313695']

    
    # Cria a legenda (StepColormap) com base nos Bins e Color_list
    color_map = StepColormap(colors=color_list, index=bins, vmin=bins[0], vmax=bins[-1], caption=nome_camada)

    # FUNÇÃO DE ESTILO: Aplica a cor do color_map ao polígono
    def style_function(feature):
        value = feature['properties'][coluna]
        
        # Estilo para valores zero/nulos: Transparente ou Cinza claro
        if estilo_transparente_zero and (pd.isna(value) or value < 0.01):
            return {'fillColor': '#FFFFFF', 'fillOpacity': 0.0, 'color': '#333333', 'weight': 0.5}
        
        # --- LÓGICA V27: FORÇA VERMELHO SOMENTE PARA SEM_LIXO > 0.0 ---
        elif coluna == '%_Sem_Lixo' and estilo_transparente_zero and pd.notna(value) and value >= 0.01:
            # Mantém a força do vermelho escuro para Lixo > 0.0
            return {'fillColor': '#800026', 'fillOpacity': 0.85, 'color': '#333333', 'weight': 0.5}
        # --- FIM LÓGICA V27 ---
        
        # Estilo para valores com dados (Lógica padrão do Colormap)
        elif pd.notna(value):
            final_color = color_map(value)
            return {'fillColor': final_color, 'fillOpacity': 0.85, 'color': '#333333', 'weight': 0.5} 
        
        else: 
             return {'fillColor': 'lightgray', 'fillOpacity': 0.5, 'color': '#333333', 'weight': 0.5}

    # Adiciona a camada GeoJson e Tooltip
    geojson_layer = folium.GeoJson(gdf, name=nome_camada, style_function=style_function, show=is_default_open).add_to(m)
    
    # ... (Restante do código de tooltip) ...
    tooltip_fields = ['NOME_BAIRRO', coluna]
    if coluna in ['Rendimento_Medio_Mensal', 'Preço Médio (R$/m²)']:
         tooltip_aliases = ['Bairro:', f'{nome_camada}: (R$)']
    elif coluna == 'População Total':
         tooltip_aliases = ['Bairro:', f'{nome_camada}: (Pessoas)']
    elif coluna == 'KM_CICLOVIA':
         tooltip_aliases = ['Bairro:', f'{nome_camada}: (km)']
    else:
         tooltip_aliases = ['Bairro:', f'{nome_camada}:']
    
    geojson_layer.add_child(GeoJsonTooltip(
             fields=tooltip_fields, aliases=tooltip_aliases, localize=True, 
             style=("background-color: white; color: #333333; font-family: sans-serif; font-size: 14px; padding: 10px;"), sticky=True
           )
    )

# ===============================================================
# FUNÇÃO 2: NOVA FUNÇÃO PARA CAMADAS COMBINADAS (V25)
# ===============================================================

def criar_camada_combinada(m, gdf, col_acesso, col_carencia, nome_camada, is_default_open=False, limite_transparencia=10.0):
    """
    Cria uma camada GeoJson combinada (Roxo Acesso / Vermelho Carência).
    V25: Sem Legenda. Laranja para Esgoto Neutro/Próximo (se |DIF_SCORE| < limite).
    """
    
    # 1. Pré-cálculo da Diferença de Acesso/Carência (Acesso - Carência)
    gdf['DIF_SCORE'] = gdf[col_acesso] - gdf[col_carencia]
    
    valid_data = gdf['DIF_SCORE'].dropna()
    if valid_data.empty:
        print(f"Aviso: Dados insuficientes para criar a camada combinada '{nome_camada}'.")
        return

    min_val = valid_data.min() # Maior carência (vermelho extremo)
    max_val = valid_data.max() # Maior acesso (roxo extremo)
    
    # 2. Definição do Mapa de Cores (LinearColormap)
    breakpoints = [min_val, -20.0, -10.0, 0.0, 10.0, 20.0, max_val]
    breakpoints = sorted(list(set([b for b in breakpoints if b >= min_val and b <= max_val])))

    if len(breakpoints) >= 7:
        colors = ['#800026', '#e31a1c', '#fd8d3c', '#FFFFFF', '#b3cde3', '#8c96c6', '#4a1486']
    elif len(breakpoints) >= 5:
        colors = ['#800026', '#e31a1c', '#FFFFFF', '#8c96c6', '#4a1486']
    else: 
        colors = ['#800026', '#FFFFFF', '#4a1486']
        breakpoints = [min_val, 0.0, max_val]

    map_min_val = min(breakpoints)
    map_max_val = max(breakpoints)

    color_map = LinearColormap(colors=colors, index=breakpoints, vmin=map_min_val, vmax=map_max_val, caption=nome_camada)
    
    # 3. Função de Estilo
    def style_function(feature):
        value = feature['properties']['DIF_SCORE']
        carencia_valor = feature['properties'][col_carencia] # Valor percentual de carência
        
        if pd.notna(value):
            final_color = color_map(value)
            
            # --- TRATAMENTO ESPECIAL LIXO: PRIORIDADE TOTAL PARA CARÊNCIA DE LIXO > 0.0 ---
            if col_carencia == '%_Sem_Lixo' and carencia_valor > 0.0: 
                
                # Força a cor para o vermelho mais escuro (map_min_val) para sinalizar o problema.
                final_color = color_map(map_min_val) 
                return {'fillColor': final_color, 'fillOpacity': 0.85, 'color': '#333333', 'weight': 0.5} 
            
            # Lógica de NEUTRO/PRÓXIMO: Aplica Laranja ou Transparente 
            if abs(value) < limite_transparencia:
                if col_carencia == '%_Sem_Esgoto':
                    # Aplica Laranja para Esgoto Neutro/Próximo (cor '#fd8d3c')
                    return {'fillColor': '#fd8d3c', 'fillOpacity': 0.7, 'color': '#333333', 'weight': 0.5}
                else:
                    # Continua transparente para outras combinações (ex: se Lixo for exatamente 0.0)
                    return {'fillColor': '#FFFFFF', 'fillOpacity': 0.0, 'color': '#333333', 'weight': 0.5}
                 
            # Caso contrário, aplica a cor baseada no DIF_SCORE (roxo ou vermelho claro/médio)
            return {'fillColor': final_color, 'fillOpacity': 0.85, 'color': '#333333', 'weight': 0.5} 
        else: 
             return {'fillColor': 'lightgray', 'fillOpacity': 0.5, 'color': '#333333', 'weight': 0.5}

    # 4. Adiciona a camada GeoJson e Tooltip
    geojson_layer = folium.GeoJson(gdf, name=nome_camada, style_function=style_function, show=is_default_open).add_to(m)
    
    tooltip_fields = ['NOME_BAIRRO', col_acesso, col_carencia]
    tooltip_aliases = ['Bairro:', f'{col_acesso}:', f'{col_carencia}:']
    geojson_layer.add_child(GeoJsonTooltip(fields=tooltip_fields, aliases=tooltip_aliases, localize=True, style=("background-color: white; color: #333333; font-family: sans-serif; font-size: 14px; padding: 10px;"), sticky=True))


# ===============================================================
# FUNÇÃO 3: CRIAÇÃO DE CAMADA DE PONTOS (INALTERADA)
# ===============================================================
def criar_camada_pontos(m, gdf, coluna_contagem, nome_camada, cor='darkblue', is_default_open=False, coluna_tooltip=None, tooltip_alias=None):
    """Cria uma camada de pontos (círculos) com tamanho proporcional à contagem/valor."""
    
    coluna_tamanho = coluna_contagem
    gdf_pontos = gdf[gdf[coluna_tamanho].fillna(0) > 0].copy()
    if gdf_pontos.empty:
        print(f"Aviso: Nenhuma contagem > 0 para a camada '{nome_camada}'. Camada não criada.")
        return
        
    if coluna_tooltip is None:
        coluna_tooltip = coluna_tamanho
        tooltip_alias = "Contagem:"
        if coluna_tamanho == 'KM_CICLOVIA':
            tooltip_alias = "KM Ciclovia:"
    
    max_val = gdf_pontos[coluna_tamanho].max()
    gdf_pontos['size'] = 5 + (gdf_pontos[coluna_tamanho] / max_val) * 20 
    
    fg = folium.FeatureGroup(name=nome_camada, show=is_default_open)
    
    for idx, row in gdf_pontos.iterrows():
        if row.geometry and row.geometry.geom_type == 'Polygon':
            centroide = row.geometry.centroid
        else: continue
        
        tooltip_value = row[coluna_tooltip]
        
        if coluna_tamanho == 'KM_CICLOVIA':
            tooltip_text = f"<b>{row['NOME_BAIRRO']}</b> | {tooltip_alias} {tooltip_value:.2f} km"
        else:
            tooltip_text = f"<b>{row['NOME_BAIRRO']}</b> | {tooltip_alias} {int(tooltip_value)}"
             
        folium.CircleMarker(
            location=(centroide.y, centroide.x), radius=row['size'], color=cor, 
            fill=True, fill_color=cor, fill_opacity=0.6,
            tooltip=tooltip_text
        ).add_to(fg)
    
    fg.add_to(m)


# --- FUNÇÃO PRINCIPAL ---

def cria_mapa():
    
    # --- 1. CARREGAMENTO E PREPARAÇÃO DOS DADOS ---
    if not os.path.exists(ARQUIVO_GPKG) or not os.path.exists(ARQUIVO_DADOS) or not os.path.exists(ARQUIVO_DEMOGRAFIA):
        print("ERRO: Arquivos de dados obrigatórios ausentes. Verifique os caminhos.")
        return
        
    # CORREÇÃO PARA LEITURA DE ARQUIVO XLSX
    if not os.path.exists(ARQUIVO_PRECO_M2):
        print(f"AVISO: Arquivo de preço por m² '{ARQUIVO_PRECO_M2}' não encontrado. A camada 17 não será criada.")
        df_preco_m2 = pd.DataFrame()
    else:
         try:
            # LEITURA CORRIGIDA: pd.read_excel em vez de pd.read_csv
            df_preco_m2 = pd.read_excel(ARQUIVO_PRECO_M2) 
            df_preco_m2 = df_preco_m2[['Bairro', 'Preço Médio (R$/m²)']].copy()
            df_preco_m2['NM_BAIRRO_NORMALIZADO'] = df_preco_m2['Bairro'].apply(normalizar_nome)
            print("1.1. Dados de Preço/m² carregados com sucesso (via XLSX reader).")
         except Exception as e:
            print(f"ERRO ao carregar o arquivo de preço/m² como XLSX: {e}")
            df_preco_m2 = pd.DataFrame()

    print("1. Carregando dados geográficos e de atributos...")
    
    try:
        gdf_setores = gpd.read_file(ARQUIVO_GPKG)
        df_final = pd.read_excel(ARQUIVO_DADOS)
        df_demografia = pd.read_excel(ARQUIVO_DEMOGRAFIA) 
    except Exception as e:
        print(f"ERRO ao carregar arquivos: {e}")
        return

    # 2. Preparação dos Dados e Geometria dos Bairros
    gdf_setores['CD_MUN_EXTRAIDO'] = gdf_setores['CD_SETOR'].astype(str).str[:7].str.strip()
    gdf_fortaleza = gdf_setores[gdf_setores['CD_MUN_EXTRAIDO'] == CODIGO_FORTALEZA_STR].copy()
    gdf_bairros = gdf_fortaleza.dissolve(by='NM_BAIRRO', aggfunc='first').reset_index()
    
    df_final['NM_BAIRRO_NORMALIZADO'] = df_final['Bairro'].apply(normalizar_nome)
    gdf_bairros['NM_BAIRRO_NORMALIZADO'] = gdf_bairros['NM_BAIRRO'].apply(normalizar_nome)
    
    df_demografia = df_demografia[df_demografia['Campo'] == 'População Total'].copy()
    df_demografia['NM_BAIRRO_NORMALIZADO'] = df_demografia['Bairro'].apply(normalizar_nome)
    df_demografia = df_demografia[['NM_BAIRRO_NORMALIZADO', 'População Total']].copy()
    
    colunas_interesse = ['NM_BAIRRO_NORMALIZADO', 'ICS', 'CARÊNCIA_ESGOTO', 'CARÊNCIA_LIXO', 
                         'CARÊNCIA_FINANCEIRA', 'CARÊNCIA_MOBILIDADE', 'CARÊNCIA_EDUCACAO', 'Bairro', 
                         'rede_geral', 'nao_rede', 'Coletado', 'nao_coletado', '%_Acesso_Esgoto',
                         '%_Sem_Esgoto', '%_Coleta_Lixo', '%_Sem_Lixo', 'Total_Vagas_ZA', 
                         'Total_Estacoes', 'Total_IES', 'Total_Farmacias_OSM', 'Total_Financeiros_OSM', 'KM_CICLOVIA',
                         'Rendimento_Medio_Mensal'] 
    
    df_merge = df_final[colunas_interesse].copy()

    gdf_final = gdf_bairros.merge(df_merge, on='NM_BAIRRO_NORMALIZADO', how='left').rename(columns={'Bairro': 'NOME_BAIRRO'}).dropna(subset=['rede_geral']) 
    gdf_final = gdf_final.merge(df_demografia, on='NM_BAIRRO_NORMALIZADO', how='left')
    
    # NOVO MERGE: Preço por m²
    if not df_preco_m2.empty:
         # Garantir que o preço seja numérico para o mapa
         df_preco_m2['Preço Médio (R$/m²)'] = pd.to_numeric(df_preco_m2['Preço Médio (R$/m²)'], errors='coerce')
         gdf_final = gdf_final.merge(df_preco_m2[['NM_BAIRRO_NORMALIZADO', 'Preço Médio (R$/m²)']], on='NM_BAIRRO_NORMALIZADO', how='left')


    if gdf_final.crs and gdf_final.crs != 'EPSG:4326':
        print(f"  -> Reprojetando bairros de {gdf_final.crs} para EPSG:4326...")
        gdf_final = gdf_final.to_crs(epsg=4326)
    
    print(f"  -> Geometria unida com {len(gdf_final)} bairros.")

    # 3. Criação do Mapa Base
    fortaleza_center = [-3.7319, -38.5267]
    m = folium.Map(location=fortaleza_center, zoom_start=11, tiles='CartoDB Positron')
    
    # --- 4. CRIAÇÃO DAS 14 CAMADAS ORIGINAIS ---
    print("4. Criando as 14 camadas originais (Sem Legenda)...")
    
    # Camadas Coropléticas (1 a 8)
    criar_camada_coropletica(m, gdf_final, '%_Acesso_Esgoto', '1. Acesso à Rede de Esgoto (%)', cmap='YlGn', is_default_open=True)
    criar_camada_coropletica(m, gdf_final, '%_Sem_Esgoto', '2. Domicílios SEM Rede de Esgoto (%)', cmap='YlOrRd', estilo_transparente_zero=True)
    criar_camada_coropletica(m, gdf_final, '%_Coleta_Lixo', '3. Domicílios com Coleta de Lixo (%)', cmap='YlGn')
    criar_camada_coropletica(m, gdf_final, '%_Sem_Lixo', '4. Domicílios SEM Coleta de Lixo (%)', cmap='YlOrRd', estilo_transparente_zero=True)
    criar_camada_coropletica(m, gdf_final, 'KM_CICLOVIA', '5. Quilometragem de Ciclovia (km)', cmap='YlGn', is_default_open=False)
    criar_camada_coropletica(m, gdf_final, 'Rendimento_Medio_Mensal', '6. Rendimento Médio Mensal (R$)', cmap='YlGn', is_default_open=False) 
    criar_camada_coropletica(m, gdf_final, 'População Total', '7. População Total', cmap='YlGn', is_default_open=False)
    criar_camada_coropletica(m, gdf_final, 'ICS', '8. Índice de Condição de Serviço (ICS)', cmap='RdYlGn', is_default_open=False)

    
    # Camadas de Pontos (9 a 13)
    print("4.1. Criando camadas de pontos (9 a 13)...")
    criar_camada_pontos(m, gdf_final, 'Total_Vagas_ZA', '9. Vagas de Zona Azul (Contagem)', cor='darkblue')
    criar_camada_pontos(m, gdf_final, 'Total_Estacoes', '10. Estações de Bicicleta (Contagem)', cor='darkgreen') 
    criar_camada_pontos(m, gdf_final, 'Total_IES', '11. Instituições de Ensino Superior (Contagem)', cor='purple')
    criar_camada_pontos(m, gdf_final, 'Total_Farmacias_OSM', '12. Farmácias (Contagem OSM)', cor='darkred')
    criar_camada_pontos(m, gdf_final, 'Total_Financeiros_OSM', '13. Instituições Financeiras (Contagem OSM)', cor='orange')
    
    
    # Camada de Linhas (14)
    print("4.2. Adicionando camada 14: ciclofaixas de lazer (traçado)...")
    if os.path.exists(ARQUIVO_CICLOFAIXA_LAZER):
        try:
            df_ciclofaixa = pd.read_csv(ARQUIVO_CICLOFAIXA_LAZER)
            df_ciclofaixa['geometry'] = df_ciclofaixa['The_geom'].apply(wkt.loads)
            gdf_ciclofaixa_lazer = gpd.GeoDataFrame(df_ciclofaixa, geometry='geometry', crs='EPSG:4326')
            
            if not gdf_ciclofaixa_lazer.empty:
                gdf_joined = gpd.sjoin(gdf_ciclofaixa_lazer.explode(ignore_index=True), gdf_final[['NOME_BAIRRO', 'geometry']].copy(), how='inner', predicate='intersects')
                
                if not gdf_joined.empty:
                    fg_ciclofaixa = folium.FeatureGroup(name='14. Ciclofaixa de Lazer (Traçado c/ Bairros)', show=False).add_to(m)
                    def style_ciclofaixa_final(feature):
                        return { 'color': '#FFFF00', 'weight': 6, 'opacity': 1, 'dashArray': '10, 5', 'fillOpacity': 0 }
                    
                    folium.GeoJson(
                        gdf_joined, style_function=style_ciclofaixa_final,
                        tooltip=folium.GeoJsonTooltip(fields=['NOME_BAIRRO', 'Rota'], aliases=['Bairro:','Rota:'], labels=True) 
                    ).add_to(fg_ciclofaixa)
                    print("  -> Camada 'Ciclofaixa de Lazer' adicionada (14).")
                else:
                    print("AVISO: Nenhuma linha da ciclofaixa intersecta os polígonos dos bairros (14).")
        except Exception as e:
            print(f"ERRO CRÍTICO ao adicionar a camada de ciclofaixa de lazer: {e}")

    # --- 5. CRIAÇÃO DAS NOVAS CAMADAS COMBINADAS (15 e 16) ---
    print("\n5. Criando as 2 novas camadas combinadas (Roxo Acesso <-> Vermelho Carência)...")

    # 15. Esgoto Combinado (Roxo/Vermelho/LARANJA NEUTRO)
    criar_camada_combinada(m, gdf_final, 
                           col_acesso='%_Acesso_Esgoto', 
                           col_carencia='%_Sem_Esgoto', 
                           nome_camada='15. COMBINADA: Esgoto (Roxo Acesso / Vermelho Carência - Laranja Neutro)', 
                           is_default_open=False,
                           limite_transparencia=10.0) 
                           
    # 16. Lixo Combinado (Roxo/Vermelho - Carência > 0) 
    criar_camada_combinada(m, gdf_final, 
                           col_acesso='%_Coleta_Lixo', 
                           col_carencia='%_Sem_Lixo', 
                           nome_camada='16. COMBINADA: Lixo (Roxo Acesso / Vermelho Carência - Carência > 0)', 
                           is_default_open=False,
                           limite_transparencia=1.0) 
    
    # --- 6. NOVA CAMADA INDIVIDUAL: PREÇO MÉDIO DO M² (17) ---
    if 'Preço Médio (R$/m²)' in gdf_final.columns:
         print("6. Criando nova camada: Preço Médio do M² (17)...")
         criar_camada_coropletica(m, gdf_final, 
                                  coluna='Preço Médio (R$/m²)', 
                                  nome_camada='17. Preço Médio M² (R$)', 
                                  cmap='YlOrBr', 
                                  is_default_open=True,
                                  estilo_transparente_zero=False)
    else:
        print("AVISO: Coluna 'Preço Médio (R$/m²)' não disponível. Camada 17 não criada.")
                           

    # 7. Adicionar Controle de Camadas
    LayerControl().add_to(m) 

    # 8. Salvar o Mapa
    m.save(ARQUIVO_MAPA_SAIDA)
    
    print("\n--- MAPA CONCLUÍDO ---")
    print(f"✅ Mapa interativo com 17 camadas (Sem Legendas) salvo em: {ARQUIVO_MAPA_SAIDA}")

# Executar a função
if __name__ == '__main__':
    cria_mapa()