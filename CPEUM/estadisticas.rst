""""""""""""
Estadísticas
""""""""""""

Este sitio reconstruye el desarrollo legislativo de la Constitución
Política de los Estados Unidos Mexicanos (CPEUM) desde su versión
original de 1917 hasta el día de hoy. Cada decreto de reforma se
documenta en su apartado, y en este se presentan algunas estadísticas
generales sobre ese largo proceso de reformas.

Metodología
-----------

Cada decreto constitucional está representado como un *commit* en el
repositorio. El mensaje de cada *commit* registra, entre otras cosas,
los artículos modificados y el presidente que firmó el decreto publicado
en el Diario Oficial de la Federación.

Las gráficas siguientes se generan automáticamente a partir del
historial de *commits* del repositorio por medio del script
`scripts/generar_graficos.py`_:

.. _scripts/generar_graficos.py:
   https://github.com/ceyusa/cpeum/blob/main/scripts/generar_graficos.py

Reformas por presidencia
------------------------

La siguiente gráfica muestra cuántas reformas constitucionales se
publicaron durante cada presidencia, desde Venustiano Carranza hasta la
actualidad. Cada barra equivale a un decreto de reforma registrado en el
repositorio.

.. image:: graficos/reformas_por_presidente.svg
   :align: center
   :alt: Número de reformas constitucionales por presidencia

Note cómo el número de reformas varía considerablemente entre
presidencias: algunos periodos concentran un gran número de decretos,
mientras que en otros fueron escasos.

Artículos modificados por presidencia
-------------------------------------

Esta gráfica indica cuántos artículos de la Constitución fueron
modificados durante cada presidencia. Un mismo artículo modificado en
varias ocasiones (incluso dentro de la misma presidencia) se cuenta una
sola vez por cada decreto. Los artículos transitorios no se incluyen en
este conteo.

.. image:: graficos/articulos_por_presidente.svg
   :align: center
   :alt: Número de artículos modificados por presidencia

Líneas nuevas o modificadas por presidencia
-------------------------------------------

La siguiente gráfica mide el tamaño de cada reforma en términos de
líneas de texto. Para ello se suman las líneas añadidas o modificadas
(las adiciones del *diff*) de los artículos y transitorios que
intervenía cada decreto. Es una aproximación a la extensión y alcance de
la actividad reformadora de cada presidencia.

.. image:: graficos/lineas_por_presidente.svg
   :align: center
   :alt: Líneas nuevas o modificadas por presidencia

Veces que ha sido reformado cada artículo
-----------------------------------------

Por último, esta gráfica muestra cuántas veces ha sido reformado cada
artículo de la Constitución, de mayor a menor. Ofrece una visión clara
de cuáles son los artículos con mayor actividad reformadora a lo largo
de más de un siglo. Los artículos transitorios no se incluyen.

.. image:: graficos/reformas_por_articulo.svg
   :align: center
   :alt: Número de veces que ha sido reformado cada artículo
