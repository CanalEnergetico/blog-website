# app/context.py
from .models import Articulos

def register_context(app):
    @app.context_processor
    def inject_datos_curiosos():
        datos_curiosos = [
            {
                "titulo": "Más del 75% de la electricidad de Panamá proviene de fuentes renovables.",
                "contenido": "Esto se debe principalmente a la hidroenergía, que históricamente ha representado la mayor parte de la generación eléctrica del país, seguida por la energía solar y eólica en crecimiento.",
                "fuente": "Secretaría Nacional de Energía de Panamá, Informe Energético Nacional 2022."
            },
            {
                "titulo": "Panamá fue el primer país de Centroamérica en tener una planta de gas natural licuado (GNL).",
                "contenido": "La planta de AES Colón, inaugurada en 2018, introdujo el GNL en la región con el objetivo de diversificar la matriz energética y mejorar la seguridad del suministro.",
                "fuente": "AES Panamá - aespanama.com"
            },
            {
                "titulo": "El Canal de Panamá genera su propia energía a través de plantas hidroeléctricas internas.",
                "contenido": "La Autoridad del Canal de Panamá opera las plantas de Gatún y Madden, que abastecen parte del consumo energético del propio canal y sus operaciones.",
                "fuente": "Autoridad del Canal de Panamá (ACP), Informe Anual 2023."
            },
            {
                "titulo": "Panamá importa el 100% de los combustibles fósiles que consume.",
                "contenido": "El país no cuenta con reservas propias de petróleo, gas o carbón, por lo que depende totalmente de las importaciones para suplir la demanda de derivados del petróleo, especialmente en el sector transporte.",
                "fuente": "Secretaría Nacional de Energía de Panamá, Balance Energético Nacional 2022."
            },
            {
                "titulo": "El sector transporte es el mayor consumidor de energía en Panamá.",
                "contenido": "Representa más del 40% del consumo energético final del país, superando ampliamente al sector residencial e industrial. Esta tendencia ha impulsado políticas públicas hacia la electromovilidad y la eficiencia en transporte público.",
                "fuente": "Secretaría Nacional de Energía de Panamá, Política Energética 2020–2050."
            },
            {
                "titulo": "Panamá tiene uno de los niveles más altos de electrificación en América Latina.",
                "contenido": "Cerca del 95% de la población panameña tiene acceso a electricidad, gracias a los esfuerzos de expansión de redes y proyectos de electrificación rural.",
                "fuente": "Banco Interamericano de Desarrollo (BID), Informe de Acceso Energético 2023."
            },
            {
                "titulo": "La energía solar ha crecido más de 10 veces en capacidad instalada desde 2015.",
                "contenido": "Gracias a políticas de incentivos y reducción de costos tecnológicos, Panamá ha incrementado considerablemente su capacidad solar, alcanzando más de 250 MW instalados en 2023.",
                "fuente": "ASEP Panamá, Estadísticas Energéticas 2023."
            },
            {
                "titulo": "Panamá busca ser un hub energético regional para Centroamérica y el Caribe.",
                "contenido": "Con su posición geográfica y la infraestructura del Canal, el país apuesta por convertirse en un centro de distribución de energías limpias, incluyendo hidrógeno verde y gas natural licuado.",
                "fuente": "Secretaría Nacional de Energía, Estrategia Nacional de Transición Energética 2020–2050."
            }]
        return dict(datos_curiosos=datos_curiosos)

    @app.context_processor
    def inject_articulos():
        articulos = Articulos.query.order_by(Articulos.id.asc()).all()
        return dict(articulos=articulos)

    # 👉 NUEVO: filtro para colores de tags
    TAG_TO_BADGE = {
        "renovables": "success",  # verde
        "combustibles": "danger",  # rojo
        "sistema eléctrico": "primary",  # azul
    }

    def tag_color(nombre: str) -> str:
        if not nombre:
            return "dark"
        n = nombre.strip().lower()

        # Combustibles fósiles
        if any(word in n for word in
               ["combustible", "gas", "oil", "petróleo", "petroleo", "diesel", "carbón", "carbon", "gas natural"]):
            return "danger"  # rojo

        # Renovables
        if any(word in n for word in
               ["renovable", "solar", "eólica", "hidrógeno", "hidrogeno", "geotérmica", "geotermica", "biomasa",
                "hidráulica", "hidraulica"]):
            return "success"  # verde

        # Sistema eléctrico
        if any(word in n for word in ["sistema eléctrico", "red eléctrica", "transmisión", "distribución", "grid"]):
            return "primary"  # azul

        # Innovación
        if "innovación" in n or "innovacion" in n:
            return "info"  # celeste

        # Movilidad
        if "movilidad" in n or "transporte" in n:
            return "primary"  # amarillo

        # Sostenibilidad
        if "sostenibilidad" in n or "sostenible" in n:
            return "success"  # verde (igual que renovables, o puedes diferenciar con "secondary")

        # Sociedad y energía
        if "sociedad" in n or "energía" in n or "energia" in n:
            return "dark"  # gris

        # Actualidad
        if "actualidad" in n or "noticia" in n:
            return "dark"

        # Default
        return "dark"

    # registra el filtro global en Jinja
    app.jinja_env.filters["tag_color"] = tag_color
