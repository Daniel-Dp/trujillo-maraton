# Plan de implementación – Maratón Internacional de Trujillo 2027

## Arquitectura
- **Frontend estático**: `index.html` (portal + modal e-ticket), `admin.html` (panel), `css/styles.css`, `js/app.js`.
- **Backend**: `server.py` (Flask) → sirve estáticos y expone API REST; Firestore (colección `registrations`) y Storage (`vouchers/`).
- **Despliegue Render**: `requirements.txt`, `render.yaml`, `gunicorn server:app`. Variables de entorno en `.env.example`.
- Modo desarrollo: si no hay credenciales Firebase, el servidor usa un almacén local JSON (`local_db.json`) y `uploads/`.

## Diseño
Negro #0A0A0A, carbón #161616, naranja #FF5500, tipografía Bebas Neue + Inter. Mobile-first, variables CSS.
Assets reales: `hero-trujillo.mp4`, `2a77c9c6.jpg` (grayscale + contrast 1.1), `bb6a0046.jpg` (poster/respaldo), `85858f28.jpg` (referencia).

## API
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/registrations` | Valida y crea inscripción (código `TRU27-XXXXXX`) |
| POST | `/api/registrations/<code>/voucher` | Sube voucher a Storage |
| POST | `/api/niubiz/session` | Stub de sesión Niubiz (requiere credenciales) |
| POST | `/api/admin/login` | Token firmado (usuario/clave por env) |
| GET | `/api/admin/registrations` | Listado + KPIs |
| POST | `/api/admin/registrations/<code>/approve` | Aprueba y envía correo |
| GET | `/api/admin/export.csv` | Exporta CSV (abre en Excel) |

## Verificación
Sintaxis Python, arranque local y prueba de flujo con el cliente de test de Flask.
