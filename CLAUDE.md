# Potrero Scout — V1

Herramienta de scouting de jugadores sudamericanos (ascenso / juveniles).
Pipeline de datos públicos + capa de IA que genera informes de scouting en texto.
Proyecto de aprendizaje: priorizar claridad y simplicidad sobre cleverness.

## Stack
- Python 3
- pandas (procesar datos)
- requests / httpx (traer datos públicos)
- Streamlit (dashboard simple)
- API de Anthropic / Claude (generar los informes de texto)

## Comandos
- Instalar dependencias: `pip install -r requirements.txt`
- Correr el dashboard: `streamlit run app.py`
- Tests (cuando existan): `pytest`

## Estilo de código
- Funciones cortas con nombres claros. Si una función no entra en la pantalla, partila.
- Comentá lo no obvio (el *por qué*), no lo obvio.
- NUNCA hardcodear API keys ni secretos: usar variables de entorno. El archivo `.env` va en `.gitignore`.

## Workflow
- Commits chicos y frecuentes, un objetivo por commit, mensajes descriptivos.
- Antes de decir "listo": correr el código y mostrar la evidencia (el output real, no afirmaciones).
- Para cambios que toquen varios archivos: proponer un plan y esperar OK antes de codear.

## IMPORTANTE — estoy aprendiendo
- Explicame en lenguaje simple QUÉ hacés y POR QUÉ en cada paso. No solo el código: el razonamiento.
- Si hay dos formas de hacer algo, decime el trade-off antes de elegir una.
