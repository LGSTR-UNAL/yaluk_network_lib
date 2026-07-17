"""yaluk_network_lib — modelado de redes eléctricas y generación de casos ATP/YALUK.

Sub-paquetes:
- Network_lib:   núcleo de red (Network, Node, Line, Configuration_Type, ...).
- Lightning_lib: modelo de descargas (Lightning, Lightning_stat, LightningChannel, Soil).
- Project_lib:   settings y API funcional para generar archivos de proyecto (proj_functions).
- plot_lib:      utilidades de graficación.

Los sub-paquetes se importan explícitamente para evitar dependencias pesadas
(scipy, pyproj, matplotlib) al importar el paquete raíz.
"""
