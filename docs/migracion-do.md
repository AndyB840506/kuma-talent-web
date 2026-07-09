# Runbook — migrar kumatalent.com de Vercel a DigitalOcean

**MIGRACIÓN EJECUTADA — DO es producción (verificado 2026-07-09).** El sitio se
sirve desde DO App Platform (header `x-do-app-origin`), static site conectado a
GitHub `AndyB840506/kuma-talent-web` branch `master` con deploy-on-push (~20s en
publicar). Para deployar: `git push origin master` — nada de Vercel CLI. Queda
pendiente solo el paso 6 (limpiar dominios del proyecto Vercel) si no se hizo.

Los pasos de abajo se conservan como referencia de cómo se hizo / rollback.

Estado al 2026-07-07: el landing nuevo ya es producción en Vercel (proyecto
`kuma-talent-web`, flujo prebuilt). Este runbook es para el paso opcional de
consolidar el hosting en DO. Requiere acceso al panel de DigitalOcean (o un
API token); no se puede ejecutar desde CLI sin eso.

## Estado actual (verificado)

- DNS zone de `kumatalent.com`: **DigitalOcean** (ns1/ns2/ns3.digitalocean.com).
- `kumatalent.com` (apex): A → Vercel. `www`: CNAME → `*.vercel-dns-017.com`.
- `app.kumatalent.com`: DO App Platform, app `hiresignal` (no se toca).
- Email `hello@kumatalent.com`: GoDaddy vía MX en el apex — records críticos
  documentados en `hiresignal/docs/dns-backup-kumatalent-2026-06-12.md`.

## Pasos

1. **Crear la app estática en DO** (Apps → Create App → GitHub
   `AndyB840506/kuma-talent-web`, branch `master`, tipo Static Site,
   `source_dir: /`, `index_document: index.html`). Deploy on push: sí.
   - El plan Starter de static sites es gratis (3 apps).
2. **Verificar la URL `*.ondigitalocean.app`** que genera: debe servir el
   landing nuevo (marker: "Vetted talent, half the cost") y cargar
   `assets/founders/andres.jpg`.
3. **Agregar dominios a la app**: `kumatalent.com` (primary) y
   `www.kumatalent.com` (redirect a primary). Como el DNS zone ya está en DO,
   elegir "We manage your domain" — DO crea los records y el cert Let's
   Encrypt solo.
4. **Confirmar en Networking → Domains → kumatalent.com** que los records
   apex A / www CNAME viejos de Vercel quedaron reemplazados por los de la
   app, y que los **MX + TXT (SPF y T6823442) siguen intactos** — si DO
   pregunta por borrar records, NUNCA aceptar borrar MX/TXT.
5. **Verificar**: `curl -sI https://kumatalent.com/` → 200 con
   `server: cloudflare`? no — debe responder DO. Marker del diseño nuevo
   presente. Probar el form de contacto y el select de vacantes en vivo.
   Email: mandar un mail de prueba a `hello@kumatalent.com`.
6. **Limpiar Vercel** (solo tras 24-48h estable): remover los dominios del
   proyecto `kuma-talent-web` en Vercel. No borrar el proyecto — sirve de
   rollback.

## Lo que se pierde al salir de Vercel (resolver en el paso 1)

- El redirect `/index.php → https://app.kumatalent.com/index.php` de
  `vercel.json` (links legacy de candidatos). Static sites de DO no hacen
  redirects; opciones: ignorarlo (los invites viejos ya expiraron) o
  manejarlo con el catchall.

## Rollback

DNS otra vez a los records de Vercel (apex A `216.198.79.1`, www CNAME al
valor `*.vercel-dns-017.com` del panel de Vercel) — el proyecto Vercel queda
intacto sirviendo la misma versión.
