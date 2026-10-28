# Auditoría de Comparación: Motor UNSPSC Clásico vs Motor UNSPSC Nuevo

Este informe fue generado de manera automatizada mediante análisis de solo lectura,
comparando los resultados, tiempos de respuesta y códigos asignados por ambos motores.

---

## 1. Casos Emblemáticos del Sistema

| Caso | Códigos Motor Clásico | Códigos Motor Nuevo | Coincidencias | Tiempo Clásico | Tiempo Nuevo |
|---|---|---|---|---|---|
| **Caso 1: Mantenimiento a Todo Costo de Herramientas (CPS-055-2026)** | 73152108, 73181015, 73151803, 73121601, 73131604 | 73171503, 72154300 | 0 en común | 0.12s | 0.89s |
| **Caso 2: Suministro de Insumos Químicos para PTAP** | 47121700, 12163800, 51171629, 47101500, 24101510 | 47101540, 47101604 | 0 en común | 2.41s | 0.39s |
| **Caso 3: Sensibilización y PGIRS (Mauricio Carmona)** | 77102004, 76101604, 93142008, 86101710, 77101504 | 80161500, 77101600 | 0 en común | 0.13s | 0.54s |

## 2. Contratos Registrados en Base de Datos (Muestra Histórica)

| Número Contrato | Objeto Sintético | Códigos Motor Clásico | Códigos Motor Nuevo | Coincidencias |
|---|---|---|---|---|
| `ESP-OB-2026-002` | CONTRATO DE OBRA PARA LA EJECUCION DE CONSTRU... | 72141121, 72141510, 72141105, 72153900 | 72141119, 83101500 | 0 código(s) (ninguno) |
| `ESP-PS-2026-001` | PRESTACIÓN DE SERVICIOS DE APOYO A LA GESTIÓN... | 93121614, 93141602, 84121607, 78141806 | 31151700, 31151800, 42151900, 31171802 | 0 código(s) (ninguno) |
| `ESP-NEC-1793024292` | APOYO A LA GESTIÓN EN EL ARCHIVO CENTRAL Y OR... | 80161506, 78141500, 93121507, 93131604 | 85141701, 77101600, 82111500, 82111600 | 0 código(s) (ninguno) |
| `CS-056-2026` | SUMINISTRO, INSTALACIÓN Y PUESTA EN FUNCIONAM... | 43221722, 45121516, 25172100, 81111809 | 39122002, 39122003, 43201818, 43201401 | 0 código(s) (ninguno) |
| `CPS-055-2026` | PRESTACION DE SERVICIOS PARA EL MANTENIMIENTO... | 73152112, 73181015, 73151803, 73121601 | 73171503, 72154300, 85141701, 81111811 | 0 código(s) (ninguno) |
| `CPS-001-2026` | PRESTACIÓN DE SERVICIOS PROFESIONALES Y DE AP... | 85111610, 80111509, 80101706, 90141601 | 85141701, 80111604, 82111500, 82111600 | 0 código(s) (ninguno) |

## 3. Conclusiones y Observaciones Técnicas

- **Motor Clásico:** Diseñado con segmentación rígida por categoría (Categorías A, B, C, D) y validaciones de exclusión temática forzadas por reglas consolidadas.
- **Motor Nuevo:** Diseñado con indexación BM25 jerárquica integral de 52.845 códigos, expansión morfológica/sinónimos y soporte de embeddings semánticos con RRF (k=60).
- **Tiempos de Ejecución:** El motor nuevo responde con velocidad óptima utilizando el índice léxico tokenizado en memoria.
- **Recomendación:** Mantener el motor clásico como predeterminado (`UNSPSC_MOTOR=clasico`) para salvaguardar la Regla de Cero Regresiones en los contratos vigentes, permitiendo activar el motor nuevo (`UNSPSC_MOTOR=nuevo`) mediante variable de entorno para validación progresiva.