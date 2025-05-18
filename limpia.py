import pandas as pd
import numpy as np
import unicodedata
import re

def limpiar_tabla(df):
    def limpiar_celda(celda):
        if pd.isna(celda):
            return np.nan
        celda = str(celda)
        # Eliminar caracteres invisibles (espacios, tabs, saltos de línea, no-break spaces, etc.)
        celda = celda.replace('\xa0', ' ').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        celda = celda.strip()
        if celda == '':
            return np.nan
        # Eliminar tildes
        celda = unicodedata.normalize('NFKD', celda).encode('ASCII', 'ignore').decode('utf-8')
        # Eliminar comillas
        celda = celda.replace('"', '').replace("'", '')
        # Eliminar caracteres especiales
        celda = re.sub(r'[^\w\s]', '', celda)
        # Reemplazar espacios por guión bajo
        celda = celda.replace(' ', '_')
        return celda

    df = df.applymap(limpiar_celda)
    
    # Eliminar columna ACC_TYPE si existe
    if "ACC_TYPE" in df.columns:
        df.drop(columns=["ACC_TYPE"], inplace=True)

    return df

# Uso:
if __name__ == "__main__":
    df = pd.read_csv(r"C:\Users\mi compu\Documents\POIs\POI_4815440.csv")
    print("Contenido exacto de la celda [2, 8]:", repr(df.iloc[2, 8]))
    df_limpio = limpiar_tabla(df)
    df_limpio.to_csv("POI_4815440_CLEAN.csv", index=False, na_rep='NaN')
