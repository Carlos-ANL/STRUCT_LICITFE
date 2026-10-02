# Bot Telegram – Contrataciones menores (SEACE): Ferretería y EPP

Revisa el buscador de contrataciones ≤ 8 UIT de SEACE (Bienes, Vigentes), filtra por 50 palabras
clave de ferretería y EPP y te envía por Telegram solo lo nuevo. Corre en GitHub Actions
a las **12:00, 17:00 y 21:00 (hora de Lima)**. Cada corrida revisa desde la anterior,
y el archivo `seen_ferreteria.json` evita repetidos.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `contratos_menores.py` | Script principal |
| `keywords.py` | Las 50 palabras clave (editable) |
| `requirements.txt` | Dependencias de Python |
| `seen_ferreteria.json` | Memoria de lo ya enviado (déjalo como `{}` al inicio) |
| `.github/workflows/contratos-menores.yml` | Programación automática |

---

## PARTE 1 – Crear el bot de Telegram

1. En Telegram busca **@BotFather** (con la marca azul de verificado) y ábrelo.
2. Envía `/newbot`.
3. Escribe un **nombre** (ej. `Licitaciones Ferretería`) y luego un **usuario** que termine en `bot` (ej. `licit_ferreteria_bot`).
4. BotFather te dará un **token** parecido a `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxx`. Cópialo y guárdalo. **No lo compartas ni lo subas al código.**
5. Abre tu nuevo bot y pulsa **Iniciar** (o envíale cualquier mensaje, por ejemplo "hola"). Sin este paso el bot no puede escribirte.

### Obtener tu CHAT_ID

1. Con el mensaje del paso 5 ya enviado, abre en el navegador (cambia `TU_TOKEN`):
   `https://api.telegram.org/botTU_TOKEN/getUpdates`
2. Busca `"chat":{"id":123456789,...}`. Ese número es tu **CHAT_ID**.
3. Si no aparece nada, envía otro mensaje al bot y recarga la página.

**Si prefieres recibirlo en un grupo:** crea el grupo, agrega el bot, escribe un mensaje en el grupo y repite `getUpdates`. El id de un grupo es **negativo** (ej. `-1001234567890`); úsalo completo, con el signo menos.

---

## PARTE 2 – Subir el proyecto a GitHub

1. Entra a github.com → **New repository**. Nombre sugerido: `bot-ferreteria-epp`.
   Puede ser público (ejecuciones gratis sin límite) o privado (2000 minutos gratis al mes; este bot usa muy poco).
2. Sube **todos** los archivos, incluida la carpeta `.github/workflows/`.
   - **Con la web:** *Add file → Upload files* y arrastra el contenido de la carpeta. Verifica después que en el repo aparezca `.github/workflows/contratos-menores.yml`. Si no se subió, usa *Add file → Create new file*, escribe `.github/workflows/contratos-menores.yml` como nombre y pega el contenido.
   - **Con git:**
     ```
     git init
     git add .
     git commit -m "bot ferreteria epp"
     git branch -M main
     git remote add origin https://github.com/TU_USUARIO/bot-ferreteria-epp.git
     git push -u origin main
     ```

## PARTE 3 – Configurar GitHub

1. **Secretos:** repo → **Settings → Secrets and variables → Actions → New repository secret**. Crea dos:
   - `TELEGRAM_TOKEN` = el token de BotFather
   - `TELEGRAM_CHAT_ID` = tu chat id
2. **Permisos:** **Settings → Actions → General → Workflow permissions** → marca **Read and write permissions** → *Save*. (Necesario para que el bot guarde `seen_ferreteria.json` y no te repita avisos.)
3. Verifica que Actions esté habilitado en la pestaña **Actions**.

## PARTE 4 – Probar

1. Pestaña **Actions** → **contratos-menores-ferreteria-epp** → **Run workflow**.
2. Espera 1–2 minutos. Deberías recibir en Telegram:
   - Las licitaciones de ferretería/EPP publicadas desde ayer (la primera vez puede llegar una tanda larga).
   - Un mensaje "✅ Bot ferretería/EPP activo" (una vez al día).
3. Ejecútalo otra vez: **no** debe reenviar lo anterior.

A partir de ahí corre solo a las 12:00, 17:00 y 21:00 (Lima). GitHub puede retrasar las ejecuciones programadas unos minutos.

---

## Ajustes

- **Palabras clave:** edita `keywords.py` (sin tildes, en minúsculas).
- **Horarios:** edita los `cron` del workflow. Están en UTC; Lima es UTC−5 (12:00 Lima = `17:00 UTC`).
- **Urgencia:** variable `URGENTE_HORAS` (por defecto 6): marca 🚨 si faltan esas horas o menos.
- **Avisar "sin novedades" en cada corrida:** variable `NOTIFY_EMPTY=1` (por defecto 0).
- Las variables se agregan en el workflow, bajo `env:` del paso que ejecuta el script.

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| No llega nada a Telegram | No pulsaste *Iniciar* en el bot, o el CHAT_ID está mal. Revisa `getUpdates`. |
| Error 401 / Unauthorized | Token mal copiado. Revísalo en el secreto. |
| Error 400 chat not found | CHAT_ID incorrecto. En grupos debe llevar el signo `-`. |
| Te repite avisos | Falta el permiso de escritura (Parte 3, paso 2) o se borró `seen_ferreteria.json`. |
| Falla el paso "Guardar vistos" | Mismo permiso de escritura. |
| El workflow no aparece | La carpeta `.github/workflows` no se subió bien. |
| Error al consultar SEACE | El portal pudo estar caído; el bot te avisa por Telegram y la siguiente corrida recupera lo pendiente. |

## Seguridad

- El token vive solo en los *Secrets* de GitHub, nunca en el código.
- Si crees que se filtró: en BotFather usa `/revoke`, y actualiza el secreto.
