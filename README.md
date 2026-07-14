# Presente — sistema de asistencia con reconocimiento facial

Aplicación web local que registra asistencia al reconocer el rostro de un alumno con **DeepFace**. El profesor puede dar de alta alumnos, tomar asistencia desde la cámara, consultar el historial y descargarlo como CSV.

## Funcionalidades

- Registro de alumnos con nombre, matrícula y una captura facial.
- Reconocimiento con el modelo `Facenet512` de DeepFace.
- Una sola asistencia por alumno y por día.
- Historial persistente y descarga en CSV.
- Interfaz adaptable a computadora, tableta y teléfono.
- Las fotografías no se guardan: se procesan en memoria y se conserva únicamente el embedding facial.

## Requisitos

- Python **3.10, 3.11 o 3.12** (se recomienda 3.11).
- Cámara web y un navegador moderno.
- Conexión a internet durante la primera ejecución para descargar los pesos de Facenet512.

> Este es un proyecto académico. El reconocimiento facial es un dato biométrico: solicita consentimiento, limita el acceso a la carpeta `data/` y no lo uses para tomar decisiones de alto impacto.

## Instalación y ejecución

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

En Windows, la activación del entorno es:

```powershell
.venv\Scripts\activate
```

Abre [http://127.0.0.1:8000](http://127.0.0.1:8000). Permite el acceso a la cámara cuando el navegador lo solicite.

También puedes usar el script incluido:

```bash
chmod +x start.sh
./start.sh
```

La primera inferencia tarda más porque DeepFace descarga y carga el modelo. Las siguientes son más rápidas.

## Cómo usarlo

1. Abre **Registrar alumno**.
2. Escribe nombre y matrícula, activa la cámara y pulsa **Guardar registro**. Debe aparecer exactamente un rostro, de frente y bien iluminado.
3. Abre **Tomar asistencia**, activa la cámara y pulsa **Registrar asistencia**.
4. Revisa **Historial** o pulsa **Descargar CSV**.

Para probar con varias personas, repite el alta con cada alumno. Si vuelves a registrar una matrícula existente, se actualizan su nombre y embedding.

## Datos generados

La aplicación crea automáticamente:

```text
data/
├── people.json       # Matrícula, nombre y embedding facial
└── attendance.csv    # Fecha, hora, matrícula, nombre y distancia
```

Estos archivos están ignorados por Git. Para reiniciar la demostración, detén el servidor y elimina ambos archivos; se recrearán al arrancar.

## Configuración opcional

Se pueden definir variables de entorno antes de iniciar:

| Variable | Valor predeterminado | Uso |
|---|---:|---|
| `DEEPFACE_MODEL` | `Facenet512` | Modelo de embeddings |
| `DEEPFACE_DETECTOR` | `opencv` | Detector facial |
| `FACE_DISTANCE_THRESHOLD` | `0.30` | Distancia coseno máxima aceptada |
| `ATTENDANCE_DATA_DIR` | `./data` | Carpeta de persistencia |

Un umbral menor es más estricto. La iluminación, pose, cámara y población afectan el resultado; valida el umbral con datos representativos antes de cualquier uso real.

## Arquitectura

```text
Captura del navegador
        ↓
FastAPI decodifica la imagen en memoria
        ↓
DeepFace detecta, alinea y genera embedding Facenet512
        ↓
Distancia coseno contra alumnos registrados
        ↓
Coincidencia → registro único diario en CSV
```

## Pruebas

Las pruebas no descargan modelos: sustituyen la inferencia por embeddings controlados.

```bash
pip install pytest httpx
pytest -q
```

## Estructura

```text
app/
├── main.py
└── static/
    ├── app.js
    ├── index.html
    └── style.css
tests/
└── test_app.py
requirements.txt
start.sh
```

## API principal

- `POST /api/enroll` — registra o actualiza un alumno.
- `POST /api/recognize` — reconoce y registra asistencia.
- `GET /api/attendance` — devuelve el historial; acepta `?date=AAAA-MM-DD`.
- `GET /api/attendance/export` — descarga el CSV.
- `GET /docs` — documentación interactiva generada por FastAPI.
