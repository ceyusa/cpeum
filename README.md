# Constitución Política de los Estados Unidos Mexicanos

Generador estático del sitio <https://cpeum.mx>.

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

Este repositorio es parte de un esfuerzo por reconstruir el desarrollo
legislativo de la Constitución Política de los Estados Unidos Mexicanos
desde su primera versión, de 1917 hasta el día de hoy.

Hay una [Ted Talk](https://www.ted.com/) del 2012, del profesor del NYU,
Clay Shirky, donde explica a mayor detalle este punto de encuentro entre
el quehacer legislativo y el desarrollo de software abierto:

[How the Internet will (one day) transform
government](https://www.ted.com/talks/clay_shirky_how_the_internet_will_one_day_transform_government#t-21381)

## Organización del proyecto

El proyecto se divide en dos repositorios:

* **Los datos** (los artículos, los transitorios y el historial de cada
  decreto como *commits*) viven en el repositorio
  [`cpeum-decretos`](https://github.com/ceyusa/cpeum-decretos), que se
  incorpora aquí como un *submódulo* de git en el directorio
  `cpeum-decretos/`. Cada cambio constitucional, desde 1917, está
  representado como un *commit* en la rama *main* de ese repositorio.

* **Este repositorio** es únicamente el **generador del sitio web** de
  la CPEUM. En él se mantienen los scripts de compilación y despliegue
  (`scripts/`, `run.sh`), las hojas de estilo (`css/`) y algunas páginas
  auxiliares (`CPEUM/acercade.rst` y `CPEUM/estadisticas.rst`). Utiliza
  el contenido del submódulo para producir el `.html` que se publica en
  <https://cpeum.mx/>.

Para clonar este repositorio junto con su submódulo de datos:

```bash
git clone --recurse-submodules https://github.com/ceyusa/cpeum
```

Para compilar el sitio localmente, siga el flujo de [`run.sh`](run.sh).
