# HERE Hackathon: Validación de POIs con Satélite y Geometría

Este proyecto automatiza la validación de Puntos de Interés (POIs) en una red vial utilizando imágenes satelitales de HERE y análisis geométrico. Fue desarrollado para el hackathon Guadalahacks patrocinado por HERE con el objetivo de detectar errores de mapeo comunes como POIs desactualizados, ubicaciones incorrectas o asociaciones erróneas al lado de la calle.

---

## 🧩 Problema que resolvemos

Los conjuntos de datos de POIs pueden contener errores debido a actualizaciones faltantes o geolocalización incorrecta. Este pipeline identifica cuatro tipos de problemas:

1. **POI inexistente** – El lugar ya no existe o fue removido.
2. **Ubicación incorrecta** – El POI está demasiado lejos del lugar real o mal asignado.
3. **Lado incorrecto de la calle** – El POI está asociado al lado equivocado (`L` o `R`) del segmento vial.
4. **Excepción legítima** – El POI es válido aunque parezca sospechoso.

---

## ⚙️ ¿Qué hace el pipeline?

- Une los POIs (`.csv`) con segmentos viales (`.geojson`) usando `LINK_ID`.
- Calcula el centroide del segmento para posicionar cada POI.
- Usa tiles satelitales de HERE para visualizar los puntos.
- Evalúa si el POI está en el lado correcto de la calle usando producto cruzado.
- Marca como `relink` aquellos POIs cuyo lado declarado no coincide con el lado geométrico.
- Muestra y guarda la imagen satelital del primer caso `relink` con una marca visual.
- Exporta los resultados a `.csv`, `.geojson` e imagen `.png`.

---

## ▶️ Cómo ejecutar

1. Instala las dependencias:
```bash
pip install geopandas pandas shapely requests pillow matplotlib python-dotenv
```

2. Crea un archivo .env y agrega tu API Key de HERE:
```env
HERE_API_KEY=tu_clave_aquí
```
3. Ejecuta cada archivo:
```env
python nombre_del_archivo.py
```
