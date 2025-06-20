# HERE Hackathon: POI Validation with Satellite Imagery and Geometry
This project was developed for Guadalahacks Hackathon, sponsored by HERE Technologies, to improve the accuracy of Points of Interest (POIs) in urban mapping. By combining satellite imagery with geometric analysis, we detect common mapping issues such as outdated locations, incorrect geolocation, or wrong street-side association.



---

## 🧩 Problem We Solve

POI datasets often contain errors due to lack of updates or incorrect geocoding. Our pipeline identifies four key issues:

1. **Nonexistent POI** – The place no longer exists or has been removed.
2. **Incorrect Location** – The POI is placed far from its actual location or is incorrectly assigned.
3. **Wrong Street Side** – The POI is linked to the wrong side (Left/Right) of the road segment.

4. **Legitimate Exception** – The POI looks suspicious but is actually valid.

---

## ⚙️ What the Pipeline Does

- Joins POI and street segment data using `LINK_ID` (CSV + GeoJSON).
- Computes the centroid of each segment to place the POI.
- Fetches HERE satellite tiles to visually verify POI positions.
- Evaluates geometric side using cross-product vector analysis.
- Flags mismatches between reported side and actual geometric side (relink cases).
- Generates satellite snapshots with visual markers of problematic POIs.
-  Exports outputs as `.csv`, `.geojson`, and `.png`.

---

##  📽️ Video and Presentation
📽️ **[Watch the demo video](HACKATHON%20PRESENTATION.mp4)**  
📄 **[View the presentation PDF](HERE%20Hackathon%20Solution.pdf)**

---


# HERE Hackathon: Validación de POIs con Satélite y Geometría

Este proyecto automatiza la validación de Puntos de Interés (POIs) en una red vial utilizando imágenes satelitales de HERE y análisis geométrico. Fue desarrollado para el hackathon Guadalahacks patrocinado por HERE con el objetivo de detectar errores de mapeo comunes como POIs desactualizados, ubicaciones incorrectas o asociaciones erróneas al lado de la calle.

---

## ▶️ How to Run It

1. Install dependencies:
```bash
pip install geopandas pandas shapely requests pillow matplotlib python-dotenv
```

2. Create a .env file and add your HERE API Key:
```env
HERE_API_KEY=tu_clave_aquí
```
3. Run the script:
```env
python nombre_del_archivo.py
```

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
---

## 📽️ Video y Presentación
📽️ **[Watch the demo video](HACKATHON%20PRESENTATION.mp4)**  
📄 **[View the presentation PDF](HERE%20Hackathon%20Solution.pdf)**

---

## 👩🏽 Team Members/ Autores
- Sarah Sophia Gutiérrez Villalpando
- Annete Montserrat Cedillo Mariscal
- Daniel Eden Wynter González
- Anett Martínez Vázquez

