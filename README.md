# Constitución Política de los Estados Unidos Mexicanos

## Introducción

Las leyes, en última instancia, son textos. Las leyes son textos
organizados, vigilados y legislados por aquellos individuos que se rigen
colectivamente bajo éstas.

El software también es texto en última instancia. Es texto que se
convierte en código binario para ser ejecutado por una computadora. Los
programadores de un software particular escriben, organizan y modifican
el texto que luego resultará en una aplicación en ejecución.

En la historia del desarrollo de software se han desarrollado
herramientas que facilitan a los programadores el [control del ciclo de
vida del software](https://es.wikipedia.org/wiki/Control_de_versiones).
Es decir, herramientas que facilitan el fino control de los cambios
realizados, autoría de los mismos, descripción del cambio y su motivos,
etcétera. Una de estas herramientas, y la más usada hasta ahora, es
[Git](https://es.wikipedia.org/wiki/Git).

Git controla la evolución de textos en el tiempo. Y así como se puede
usar facilitar el desarrollo de software, también se puede utilizar para
llevar el desarrollo legislativo de las leyes.

Este repositorio es un esfuerzo por reconstruir el desarrollo
legislativo de la Constitución Política de los Estados Unidos Mexicanos
desde su primera versión, de 1917 hasta el día de hoy, donde cada
decreto constitucional se refleja como un *commit* en la rama *master*
del repositorio.

Hay una [Ted Talk](https://www.ted.com/) del 2012, del profesor del NYU,
Clay Shirky, donde explica a mayor detalle este punto de encuentro entre
el quehacer legislativo y el desarrollo de software abierto:

[How the Internet will (one day) transform
government](https://www.ted.com/talks/clay_shirky_how_the_internet_will_one_day_transform_government#t-21381)

## Estructura y formato de los archivos

El formato utilizado para almacenar es [reStructured Text
Markup](http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html),
o simplemente reST.

reST es un formato de texto plano que no requiere de ningún software
particular para visualizarlo o editarlo. Como consecuencia, cualquier
modificación que se haga puede compararse línea a linea, entre la
versión anterior y la actual, facilitando la comprensión del cambio.

Además, el formato reST tiene el soporte de una serie de herramientas de
software que permiten convertir documentos, en ese formato, a HTML,
MSWord, LateX, etc.

Ejemplo de lo anterior es que, cada vez que un nuevo decreto es empujado
como un *commit* en el repositorio, el texto en formato reST se exporta
automáticamente a una página HTML y se almacena en

<http://ceyusa.github.io/constitucion-mexicana/>

No obstante el formato reST tiene limitaciones que este trabajo ha
solventado con algunos *hacks*, como por ejemplo llevando enumeraciones
paralelas en ciertas fracciones que utiliza la letra ñ como ordinal.
Además, si se quiere hacer trabajo legislativo, reST claramente es
insuficiente. El propósito de este proyecto no es facilitar el trabajo
de los legisladores, sino divulgar los cambios constitucionales y
ponerlos a debate público.

Para debatir el formato utilizado en este repositorio y otros posibles,
está el *issue* abierto: [Integración con herramientas existentes
\#2](https://github.com/ceyusa/constitucion-mexicana/issues/2)

La estructura del repositorio es igualmente simple: hay un subdirectorio
llamado `CPEUM` donde cada artículo es un archivo cuyo nombre es el
número de artículo. Hay un archivo llamado `toc.rst` que es el documento
raíz, con el esqueleto de la Constitución. Así, las conversiones a otros
formatos se hacen sobre este archivo raíz.

Como estilo, los archivos de cada artículo, el número de caracteres
máximo por línea es de 72.

## Metodología

La Constitución original está en [PDF
digitalizado](http://www.diputados.gob.mx/LeyesBiblio/ref/dof/CPEUM_orig_05feb1917.pdf).
Se hizo el archivo `toc.rst` de manera manual y con un *script*
convirtió el PDF en texto plano y se separaron los artículos en
archivos.

Los decretos posteriores, desde 1921 hasta 1993, sólo están disponibles
como imágenes escaneadas, muchas veces con muy mala calidad, por lo que
resultaba imposible convertir estas imágenes a textos con un
[reconocedor óptico de
caracteres](https://es.wikipedia.org/wiki/Reconocimiento_%C3%B3ptico_de_caracteres),
por tanto, todos esos decretos se transcribieron manualmente.

Finalmente, a partir del decreto número 124, de 1993, los decretos están
disponibles en formato tanto PDF como MSWord, lo que me permitió hacer
un *script* que convirtiera el formato de MSWord a reST, para luego
copiar y pegar de manera manual.

Como pueden observar, este proceso de trabajo es altamente susceptible a
errores, por más cuidado que se ponga. Les pido, pues, que si encuentran
alguna pifia, me la hagan saber a través de un
[issue](https://github.com/ceyusa/constitucion-mexicana/issues/new/choose)
de GitHub, o, mejor aún, manden la corrección a través de un *pull
request* :)

## Trabajo futuro

Este trabajo abre las puertas a muchas otras posibles tareas. Por citar
algunas:

* Que las iniciativas constitucionales se lleven como *pull request*,
  así sería más público el debate legislativo.
* Sacar estadísticas de los cambios constitucionales, para contestar
  preguntas como ¿durante qué presidencia tuvo más cambos la
  Constitución? ¿Cómo ha sido la evolución cuantitativa de los cambios
  constitucionales? etcétera.
* Participar en debates públicos sobre cada cambio en la Constitución, a
  través de los mecanismo de *revisión de código* de GitHub.
