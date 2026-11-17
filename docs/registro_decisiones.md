# Registro de decisiones

Este documento explica **por qué** se tomó cada decisión de limpieza, transformación e imputación del pipeline, qué alternativas se consideraron y qué evidencia la respalda. Las cifras salen de ejecutar `python main.py` sobre `data/raw/` (ver `outputs/reporte_diagnostico.txt`, `outputs/reporte_validaciones.txt` y `outputs/log_ejecucion.log`).

## 1. Principios generales

1. **Los datos originales no se tocan.** `data/raw/` queda intacto y todo el procesamiento se hace sobre copias.
2. **Se leen como texto.** Así pandas no adivina tipos y los errores del archivo quedan visibles para el diagnóstico.
3. **No se inventa información.** Un valor solo se completa si existe una regla basada en los propios datos y esa regla se probó antes de aplicarla. Si no hay una fuente confiable, el valor queda como `NaN`.
4. **Nada se borra sin dejar rastro.** Las líneas que no se pueden relacionar con un pedido se guardan aparte en `northwind_huerfanas.csv`.
5. **Cada decisión se verifica.** Los controles de `src/validaciones.py` se ejecutan en cada corrida y detienen el proceso si fallan.

## 2. Decisiones de transformación

| # | Problema encontrado | Decisión | Por qué | Evidencia | Código |
|---|---|---|---|---|---|
| T1 | `orders` tiene 865 filas pero 830 `order_id` únicos: 25 filas idénticas y 10 pedidos repetidos con `ship_name` escrito con otras mayúsculas. | Se eliminan las idénticas. En los 10 conflictos se conserva la fila con más campos llenos. | Las copias solo difieren en mayúsculas de `ship_name`, así que no se pierde información. Dejar los duplicados inflaría pedidos e importes al unir. | 830 filas y 830 `order_id` únicos. | `limpieza.deduplicar_orders` |
| T2a | Espacios sobrantes (75 celdas en `orders`) y `order_id` de `order_details` con espacios o `.0` final (9). | `strip()` en todas las columnas y se quita el `.0` final. | Estos errores causaban la mayoría de las líneas sin pedido: las huérfanas bajaron de 15 a 6. | 0 celdas con espacios. | `limpieza.limpiar_texto_e_ids` |
| T2b | 43 celdas con caracteres mal codificados (`Ã¼`, `Ã±`, `Ã©`, `�`). | Se eliminan esas secuencias. | La reparación habitual de mojibake no recupera el texto original (por ejemplo `SeÃ¼attle` pasa a `Seüattle`, no a `Seattle`), lo que indica que los caracteres fueron insertados dentro de las palabras. | 0 celdas con caracteres extraños. | `limpieza.quitar_encoding` |
| T2c | 60 filas idénticas en `order_details`. | Se eliminan. | No hay conflictos por `order_id` + `product_id`: eran copias exactas. | 0 claves repetidas. | `limpieza.deduplicar_details` |
| T2d | 6 líneas con `order_id` que no existe en `orders` (19473, 19475, 19484, 19550, 19614 y A10363). | No se borran: se guardan en `northwind_huerfanas.csv`. | Parecen errores de captura de pedidos que sí existen (10473, 10475, 10484, 10550, 10614 y 10363), pero con los datos disponibles no se puede confirmar, así que corregirlos sería suponer. | 2215 = 60 + 2149 + 6. | `limpieza.separar_huerfanas` |
| T3a | `unit_price`, `quantity`, `discount` y `freight` traen `$`, `USD`, coma decimal, `%` y palabras. | Se quitan símbolos, la coma pasa a punto, los `%` se dividen entre 100 y `diez`/`cinco` se traducen. | Son formas distintas de escribir el mismo número. | Solo quedan sin convertir 14 precios (`N/A` y `free`). | `transformaciones.limpiar_numero` |
| T3b | Precio `free`. | Queda `NaN`, no 0. | El diccionario de datos exige `unit_price` > 0. Poner 0 mezclaría "gratis" con "dato desconocido". | 0 precios ≤ 0. | `transformaciones.limpiar_numero` |
| T3c | `cinco` y `diez` escritos en palabras. | En `discount`, `cinco` se toma como 5 %. | Es la lectura natural en una columna de descuentos con valores como 0.05 y 0.10. **Es un supuesto**, no hay forma de confirmarlo en los datos. | Descuentos dentro de 0 a 0.25. | `config.PALABRAS_NUMERICAS` |
| T3d | Cantidades ≤ 0, de 999 o con decimales; descuentos de -0.1 y 1.5; 4 fletes negativos. | Quedan `NaN` y no se elimina la línea. | Se conserva el resto de la información de la línea. No hay forma confiable de saber el valor correcto. | `quantity` entre 1 y 130, `discount` entre 0 y 0.25, `freight` ≥ 0. | `transformaciones.aplicar_rangos` |
| T3e | Descuentos de 0.01 a 0.06. | Se conservan: la regla es un rango de 0 a 0.25 y no una lista cerrada. | Todos pertenecen al pedido 11077, que tiene descuentos de 0.00 a 0.20 en sus líneas, por lo que se toman como propios de ese pedido y no como errores. | Ver C6 en el reporte de validaciones. | `config.DESCUENTO_MAX` |
| T4 | 8 formatos de fecha, 19 de ellas ambiguas entre día/mes y mes/día. | Con barra se lee DD/MM/AAAA y con guion MM-DD-AAAA. Los años de dos dígitos se toman como 19xx. | Entre las fechas no ambiguas, con barra el día va primero 20 veces y nunca al revés; con guion el mes va primero 17 veces y nunca al revés. Todos los pedidos son de 1996 a 1998. | La diferencia entre `order_date` y `required_date` solo da 14, 28 o 42 días. Si la regla estuviera mal saldrían diferencias raras. 0 fechas incoherentes. | `transformaciones.convertir_fechas` |
| T5a | `ship_country` con 28 variantes no estándar (mayúsculas, errores de escritura, español, siglas). | Primero se compara sin mayúsculas y luego se aplica un diccionario de equivalencias. | La lista de 21 países válidos es la que se definió en el diagnóstico del avance 1. | 50 valores distintos pasan a 22 (21 países más el vacío). | `config.EQUIVALENCIAS_PAIS` |
| T5b | `ship_name`, `ship_city`, `ship_address` con el mismo valor en distintas mayúsculas. | Se deja la forma que combina mayúsculas y minúsculas (`Ernst Handel`, no `ERNST HANDEL`). | Es la forma legible; las variantes solo en mayúsculas o solo en minúsculas son versiones alteradas del mismo texto. | 0 variantes por mayúsculas. | `transformaciones.unificar_mayusculas` |
| T5c | Errores de escritura por cliente (`Bose`, `Bise` en vez de `Boise`) que el diagnóstico inicial no contaba. | Para cada cliente se usa la forma más repetida de `ship_name`, `ship_address`, `ship_city` y `ship_postal_code`. Si hay empate no se cambia nada. | En Northwind cada cliente tiene una sola dirección de envío. Ante un empate no se sabe cuál es la correcta. | Queda solo el cliente GROSR (`GROSELLA` y `GROSSELLA`, una vez cada uno). | `transformaciones.corregir_por_cliente` |

## 3. Decisiones de imputación (valores nulos)

Todas las reglas se probaron antes de aplicarlas: se oculta un valor que sí se conoce, se estima con la regla y se cuenta cuántas veces coincide.

### 3.1 `customer_id` y datos de envío
- **Regla:** un `customer_id` vacío se completa con el cliente que tiene ese mismo `ship_name`. Los campos de envío vacíos se completan con el valor más frecuente de ese cliente.
- **Por qué:** ningún `ship_name` pertenece a más de un cliente, y cada cliente tiene una sola dirección de envío.
- **Resultado:** 14 de los 15 `customer_id` vacíos recuperados, más 11 `ship_name`, 15 `ship_city` y 10 `ship_country`. Solo 3 líneas quedan sin cliente, todas del pedido 10498, que no tenía ni cliente ni `ship_name`.
- **No se completa:** `ship_region` (507 vacíos) corresponde a clientes sin región en ningún pedido, porque no aplica a todos los países. Los 19 `ship_postal_code` vacíos son del cliente HUNGO, que no tiene código postal en ningún pedido.

### 3.2 `unit_price`
- **Alternativa descartada: promedio por producto.** De 77 productos, 75 tienen dos precios distintos y 2 tienen tres (un precio antes y otro después de un cambio de precio), así que un promedio no sirve.
- **Regla elegida:** precio del mismo producto en el pedido con `order_id` más cercano.
- **Evidencia:** acierta en 2.047 de 2.096 precios conocidos (**97,7 %**).
- **Resultado:** 38 precios completados.

### 3.3 `discount`
- **Alternativa descartada: poner siempre 0.** Habría acertado solo el 60,8 % de las veces.
- **Regla elegida:** si las otras líneas del mismo pedido tienen un solo descuento, se usa ese; si no hay de dónde sacarlo, 0.
- **Evidencia:** la regla del pedido acierta en 1.452 de 1.651 casos (**87,9 %**).
- **Resultado:** 36 descuentos completados (24 con el descuento del pedido y 12 con 0).

### 3.4 Lo que no se completa
`quantity` (29), `product_id` (15), `employee_id` (12), `freight` (29) y las fechas quedan como `NaN`: no hay una fuente confiable dentro de los datos para recuperarlos. Después de todas las transformaciones, 30 líneas quedan sin importe calculable.

## 4. Impacto de las decisiones en el importe total

| Momento | Importe total | Líneas sin importe |
|---|---|---|
| Datos originales (Control 2) | 1.254.983,16 | 76 |
| Tras limpiar y convertir (sin imputar) | 1.229.549,01 | 68 |
| Tras las imputaciones (resultado final) | 1.249.945,73 | 30 |

- Las líneas con precio imputado aportan 21.147,04, cerca del 1,7 % del importe final.
- **Sensibilidad del descuento:** si todos los descuentos vacíos se tomaran como 0 en lugar de aplicar la regla, el total sería 1.250.696,04, es decir 750,31 más (0,06 %). La decisión de imputación del descuento mueve el resultado muy poco.
- El importe es el mismo antes y después de unir las tablas (control C9).

## 5. Limitaciones y riesgos

- Las imputaciones tienen error: el precio falla en cerca del 2,3 % de los casos de prueba y el descuento en cerca del 12,1 %. Los valores imputados son estimaciones, no datos observados.
- La regla de fechas (barra = día primero, guion = mes primero) se apoya en las fechas no ambiguas del propio dataset. Es muy consistente, pero sigue siendo una inferencia.
- Las 6 líneas huérfanas no se incorporan al consolidado porque no se puede confirmar a qué pedido pertenecen.
- La interpretación de `cinco` como 5 % es un supuesto.
- Las cifras de este documento dependen de los archivos de `data/raw/`; si cambian, hay que volver a correr `python main.py` y actualizar los números.
