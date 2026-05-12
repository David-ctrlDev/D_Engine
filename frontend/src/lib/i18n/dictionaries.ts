/**
 * i18n dictionaries — Spanish (default) and English.
 *
 * Flat dot-key structure: ``t("auth.login.title")`` rather than
 * ``t.auth.login.title``. Keeps lookups trivial and allows missing-key
 * detection by comparing ``Object.keys(es)`` against ``Object.keys(en)``.
 *
 * Strings that interpolate values use ``{name}`` placeholders; the ``t``
 * helper substitutes them at call time.
 */

export const es = {
  // ----- Common ----------------------------------------------------------
  "common.cancel": "Cancelar",
  "common.save": "Guardar",
  "common.loading": "Cargando…",
  "common.copy_all": "Copiar todo",
  "common.email": "Correo electrónico",
  "common.password": "Contraseña",
  "common.confirm_password": "Confirmar contraseña",
  "common.workspace": "Espacio de trabajo",
  "common.workspace_name": "Nombre del espacio de trabajo",
  "common.code": "Código",
  "common.something_went_wrong": "Algo salió mal. Inténtalo de nuevo.",
  "common.network_error": "Error de red. Comprueba tu conexión e inténtalo de nuevo.",

  // ----- Brand -----------------------------------------------------------
  "brand.name": "dataprep",
  "brand.version_note": "Construido para equipos de datos modernos.",

  // ----- Theme toggle ----------------------------------------------------
  "theme.switch_to_dark": "Cambiar a modo oscuro",
  "theme.switch_to_light": "Cambiar a modo claro",
  "theme.toggle": "Cambiar tema",

  // ----- Locale toggle ---------------------------------------------------
  "locale.switch_to_english": "Cambiar a inglés",
  "locale.switch_to_spanish": "Cambiar a español",

  // ----- Auth layout -----------------------------------------------------
  "auth.layout.status_operational": "Status · Operational",
  "auth.layout.copyright": "© 2026 dataprep",
  "auth.layout.terms": "Términos",
  "auth.layout.privacy": "Privacidad",
  "auth.layout.security_link": "Seguridad",
  "auth.layout.status_page": "Estado",

  // ----- Login form (enterprise rewrite) ---------------------------------
  "auth.login.workspace_eyebrow": "Workspace login",
  "auth.login.tenant_prefix": "Conectándote a",
  "auth.login.tenant_default": "acme.dataprep.io",
  "auth.login.sso_google": "Continuar con Google",
  "auth.login.sso_microsoft": "Continuar con Microsoft",
  "auth.login.sso_saml": "Continuar con SAML SSO",
  "auth.login.divider": "o continúa con email",
  "auth.login.remember_device": "Recordar este dispositivo",
  "auth.login.request_access": "¿Eres nuevo? Solicita acceso",
  "auth.login.caps_lock": "Bloq Mayús activado",
  "auth.login.sso_not_configured": "{provider} aún no está configurado",
  "auth.login.sso_not_configured_sub":
    "Continúa con email y contraseña, o contacta al admin de tu workspace para habilitar SSO.",
  "auth.login.sso_error_sub":
    "Intenta nuevamente o usa email y contraseña. Si el problema persiste, contacta soporte.",
  "auth.login.sso_error.not_configured": "SSO no está configurado en este servidor",
  "auth.login.sso_error.unsupported_provider": "Proveedor SSO no soportado",
  "auth.login.sso_error.missing_state": "Sesión OAuth perdida — vuelve a iniciar",
  "auth.login.sso_error.state_mismatch": "Verificación de seguridad falló",
  "auth.login.sso_error.invalid_state": "Sesión OAuth inválida o expirada",
  "auth.login.sso_error.provider_mismatch": "Proveedor no coincide",
  "auth.login.sso_error.no_email": "El proveedor no devolvió un email",
  "auth.login.sso_error.exchange_failed": "El proveedor rechazó la solicitud",
  "auth.login.sso_error.access_denied": "Acceso denegado en el proveedor",
  "auth.login.sso_error.auth_accountinactiveerror": "Tu cuenta está desactivada",
  "auth.login.sso_error.unknown_error": "Algo salió mal con el SSO",

  // ----- Compliance badges -----------------------------------------------
  "compliance.soc2": "SOC 2 Type II",
  "compliance.iso": "ISO 27001",
  "compliance.gdpr": "GDPR",
  "compliance.tls": "TLS 1.3",
  "compliance.soc2_tooltip": "Auditado anualmente bajo SOC 2 Type II.",
  "compliance.iso_tooltip": "Certificado ISO/IEC 27001 — gestión de seguridad de la información.",
  "compliance.gdpr_tooltip": "Procesamiento conforme al Reglamento General de Protección de Datos.",
  "compliance.tls_tooltip": "Cifrado de transporte TLS 1.3 en todas las conexiones.",

  // ----- Right panel (enterprise value props) ----------------------------
  "right.eyebrow": "Integraciones nativas",
  "right.headline": "Tu stack de datos, en un solo workspace.",
  "right.sub":
    "Conecta cualquier fuente. El agente perfila, propone y limpia. Tú apruebas.",
  "right.testimonial_quote":
    "Redujimos un 80% el tiempo de preparación de datos para entrenar nuestros modelos.",
  "right.testimonial_author": "M. García",
  "right.testimonial_role": "Head of Data, Acme Inc.",
  "right.feature_one": "20+ conectores nativos",
  "right.feature_one_sub": "Postgres, Snowflake, BigQuery, S3.",
  "right.feature_two": "Perfilado automático con IA",
  "right.feature_two_sub": "Tipos, nulls, anomalías detectadas.",
  "right.feature_three": "Listo para entrenamiento",
  "right.feature_three_sub": "Training tables y context bundles.",
  "right.infra_eyebrow": "Infraestructura global",
  "right.infra_metric": "12 regiones · 99.99% SLA",
  "right.infra_sub": "Data residency configurable por workspace.",

  // ----- Login -----------------------------------------------------------
  "auth.login.eyebrow": "Iniciar sesión",
  "auth.login.title": "Bienvenido de {accent}",
  "auth.login.title_accent": "vuelta",
  "auth.login.subtitle": "Inicia sesión en tu workspace de dataprep.",
  "auth.login.forgot": "¿Olvidaste tu contraseña?",
  "auth.login.submit": "Iniciar sesión",
  "auth.login.submitting": "Iniciando sesión…",
  "auth.login.no_account": "¿Eres nuevo?",
  "auth.login.create_account": "Crea una cuenta",
  "auth.login.email_required": "Introduce un correo electrónico válido.",
  "auth.login.password_required": "La contraseña es obligatoria.",

  // ----- Register --------------------------------------------------------
  "auth.register.eyebrow": "Empieza ahora",
  "auth.register.title": "Crea tu {accent}",
  "auth.register.title_accent": "workspace",
  "auth.register.subtitle":
    "Te conviertes en propietario de un workspace nuevo. Toma 30 segundos.",
  "auth.register.workspace_placeholder": "Acme S.A.",
  "auth.register.password_hint":
    "Al menos 12 caracteres. Una frase con tres o cuatro palabras al azar funciona bien.",
  "auth.register.submit": "Crear cuenta",
  "auth.register.submitting": "Creando cuenta…",
  "auth.register.toast_success":
    "Cuenta creada. Mira la terminal del backend para el enlace de verificación.",
  "auth.register.have_account": "¿Ya tienes cuenta?",
  "auth.register.login_link": "Inicia sesión",
  "auth.register.password_too_short": "La contraseña debe tener al menos 12 caracteres.",
  "auth.register.password_too_long": "La contraseña es demasiado larga.",
  "auth.register.workspace_required": "El nombre del espacio es obligatorio.",
  "auth.register.workspace_too_long": "El nombre es demasiado largo.",

  // ----- Verify email ----------------------------------------------------
  "auth.verify.eyebrow": "Un último paso",
  "auth.verify.title": "Verifica tu correo",
  "auth.verify.subtitle": "Te enviamos un enlace de verificación a tu bandeja de entrada.",
  "auth.verify.idle":
    "Te enviamos un enlace. En desarrollo, el enlace se imprime en la terminal del backend — haz clic (o pégalo) para verificar.",
  "auth.verify.verifying": "Verificando tu correo…",
  "auth.verify.ok": "Tu correo está verificado.",
  "auth.verify.error": "No pudimos verificar este enlace.",
  "auth.verify.continue": "Continuar a iniciar sesión",
  "auth.verify.back": "Volver a iniciar sesión",
  "auth.verify.failed": "La verificación falló.",

  // ----- MFA login -------------------------------------------------------
  "auth.mfa.eyebrow": "Paso 2 de 2",
  "auth.mfa.title": "Autenticación de dos factores",
  "auth.mfa.subtitle":
    "Introduce el código de 6 dígitos de tu app de autenticación para terminar de iniciar sesión.",
  "auth.mfa.label_totp": "Código de autenticación",
  "auth.mfa.label_recovery": "Código de recuperación",
  "auth.mfa.toggle_to_recovery": "Usar un código de recuperación en su lugar",
  "auth.mfa.toggle_to_totp": "Usar el código de la app de autenticación",
  "auth.mfa.submit": "Verificar",
  "auth.mfa.submitting": "Verificando…",
  "auth.mfa.code_required": "Introduce un código.",
  "auth.mfa.code_too_long": "El código es demasiado largo.",
  "auth.mfa.code_charset": "Solo dígitos, letras, guiones y espacios.",

  // ----- Forgot password -------------------------------------------------
  "auth.forgot.eyebrow": "Recuperar acceso",
  "auth.forgot.title": "Restablecer contraseña",
  "auth.forgot.subtitle":
    "Introduce tu correo y te enviaremos un enlace para elegir una contraseña nueva.",
  "auth.forgot.submit": "Enviar enlace",
  "auth.forgot.submitting": "Enviando…",
  "auth.forgot.confirmation":
    "Si ese correo está registrado, te hemos enviado un enlace de restablecimiento. En desarrollo, el enlace aparece en la terminal del backend.",
  "auth.forgot.back": "Volver a iniciar sesión",

  // ----- Reset password --------------------------------------------------
  "auth.reset.eyebrow": "Nueva contraseña",
  "auth.reset.title": "Elige una nueva contraseña",
  "auth.reset.subtitle":
    "Elige una contraseña fuerte — al menos 12 caracteres. Una frase funciona bien.",
  "auth.reset.new_password": "Nueva contraseña",
  "auth.reset.submit": "Actualizar contraseña",
  "auth.reset.submitting": "Actualizando…",
  "auth.reset.toast_success": "Contraseña actualizada. Inicia sesión.",
  "auth.reset.invalid_link": "Enlace inválido o expirado.",
  "auth.reset.request_new": "Solicitar un enlace nuevo",
  "auth.reset.passwords_dont_match": "Las contraseñas no coinciden.",
  "auth.reset.confirm_required": "Confirma tu contraseña.",

  // ----- Topbar / Sidebar / Logout --------------------------------------
  "nav.dashboard": "Panel",
  "nav.datasets": "Datos",
  "nav.security": "Seguridad",
  "nav.logout": "Cerrar sesión",
  "nav.workspace": "Espacio",
  "nav.logout_success": "Sesión cerrada.",
  "nav.logout_failed": "No se pudo cerrar sesión.",

  // ----- Datasets list / detail / upload --------------------------------
  "datasets.title": "Tus datos",
  "datasets.subtitle": "Sube archivos o conecta una base de datos para empezar.",
  "datasets.upload_cta": "Subir archivo",
  "datasets.load_failed": "No se pudieron cargar los datasets.",
  "datasets.empty.title": "Aún no hay datos",
  "datasets.empty.body":
    "Sube un CSV para empezar. En breve podrás conectar PostgreSQL, SQL Server, Parquet y Excel.",
  "datasets.empty.cta": "Subir tu primer archivo",
  "datasets.col.name": "Nombre",
  "datasets.col.source": "Fuente",
  "datasets.col.visibility": "Visibilidad",
  "datasets.col.created": "Creado",
  "datasets.visibility.private": "Privado",
  "datasets.visibility.shared_workspace": "Todo el equipo",
  "datasets.visibility.shared_specific": "Compartido",

  "datasets.upload.title": "Subir un archivo",
  "datasets.upload.subtitle":
    "Acepta CSV, Parquet y Excel. Detectamos los tipos de columna automáticamente.",
  "datasets.upload.back": "Volver",
  "datasets.upload.name_label": "Nombre del dataset",
  "datasets.upload.name_placeholder": "Productos",
  "datasets.upload.name_hint":
    "Cómo aparecerá en la lista. Por defecto usamos el nombre del archivo.",
  "datasets.upload.file_label": "Archivo",
  "datasets.upload.drop_here": "Arrastra tu archivo aquí, o haz clic para elegir",
  "datasets.upload.drop_hint": "CSV, Parquet, Excel. Tamaño máximo: 500 MB.",
  "datasets.upload.unsupported": "Formato no soportado. Aceptamos CSV, Parquet y Excel.",
  "datasets.upload.no_file": "Elige un archivo para subir.",
  "datasets.upload.no_name": "Ponle un nombre al dataset.",
  "datasets.upload.submit": "Subir y analizar",
  "datasets.upload.submitting": "Subiendo…",
  "datasets.upload.toast_success": "Dataset creado.",

  "datasets.detail.back": "Volver a datos",
  "datasets.detail.not_found": "No encontramos este dataset.",
  "datasets.detail.load_failed": "No pudimos cargar el dataset.",
  "datasets.detail.columns_title": "Columnas detectadas ({count})",
  "datasets.detail.sample_title": "Muestra ({count} filas)",
  "datasets.detail.col.name": "Columna",
  "datasets.detail.col.type": "Tipo",
  "datasets.detail.col.sample": "Ejemplos",

  "datasets.connect_cta": "Conectar BD",
  "datasets.empty.connect": "Conectar una base de datos",

  // ----- Sources (DB connections) ---------------------------------------
  "sources.kind.postgres": "PostgreSQL",
  "sources.kind.mssql": "SQL Server",
  "sources.kind.mssql_azure": "Azure SQL",

  "sources.new.title": "Conectar una base de datos",
  "sources.new.subtitle":
    "Probamos la conexión antes de guardarla. Las credenciales se cifran al persistirse.",
  "sources.new.back": "Volver",
  "sources.new.kind": "Tipo de base de datos",
  "sources.new.name": "Nombre",
  "sources.new.name_placeholder": "Producción · Postgres",
  "sources.new.host": "Host",
  "sources.new.port": "Puerto",
  "sources.new.database": "Base de datos",
  "sources.new.user": "Usuario",
  "sources.new.password": "Contraseña",
  "sources.new.sslmode": "Modo SSL",
  "sources.new.test": "Probar conexión",
  "sources.new.test_ok": "Conexión exitosa.",
  "sources.new.test_failed": "No se pudo conectar.",
  "sources.new.connect": "Conectar y elegir tablas",
  "sources.new.created": "Fuente creada.",
  "sources.new.fill_required": "Completa los campos requeridos.",

  "sources.tables.title": "Elige tablas a importar",
  "sources.tables.subtitle":
    "Cada tabla seleccionada se registra como un dataset. Detectamos las columnas y tipos automáticamente.",
  "sources.tables.back": "Volver a datos",
  "sources.tables.filter": "Buscar por schema o nombre…",
  "sources.tables.select_all": "Seleccionar todo",
  "sources.tables.deselect_all": "Deseleccionar todo",
  "sources.tables.col.schema": "Schema",
  "sources.tables.col.name": "Tabla",
  "sources.tables.col.rows": "Filas (estimado)",
  "sources.tables.empty": "No hay tablas que coincidan.",
  "sources.tables.import": "Importar {count}",
  "sources.tables.imported": "Importadas {count} tablas como datasets.",
  "sources.tables.load_failed": "No se pudieron cargar las tablas.",

  // ----- Profiling (slice E) --------------------------------------------
  "profile.title": "Análisis de calidad",
  "profile.run": "Generar análisis",
  "profile.running": "Analizando…",
  "profile.empty": "Aún no se ha ejecutado un análisis para este dataset.",
  "profile.failed": "El análisis falló.",
  "profile.row_count": "Filas",
  "profile.col.name": "Columna",
  "profile.col.type": "Tipo",
  "profile.col.nulls": "Nulos",
  "profile.col.distinct": "Distintos",
  "profile.col.range": "Rango",
  "profile.col.top": "Más frecuentes",

  // ----- Sharing (slice F) ----------------------------------------------
  "share.title": "Compartir",
  "share.visibility_label": "Quién puede ver este dataset",
  "share.visibility.private": "Solo yo",
  "share.visibility.shared_workspace": "Todo el workspace",
  "share.visibility.shared_specific": "Personas específicas",
  "share.add_user": "Agregar persona",
  "share.add_user_placeholder": "Elige un miembro…",
  "share.no_grants": "Aún no has compartido con nadie.",
  "share.remove": "Quitar",
  "share.updated": "Visibilidad actualizada.",
  "share.granted": "Acceso concedido.",
  "share.revoked": "Acceso revocado.",

  // ----- Dashboard -------------------------------------------------------
  "dashboard.greeting": "Hola, {email}",
  "dashboard.workspace_label": "Espacio de trabajo:",
  "dashboard.welcome_title": "Bienvenido a dataprep",
  "dashboard.welcome_body_a":
    "La autenticación está funcionando. Las features de preparación de datos llegan en las próximas iteraciones: conectores de fuentes, perfilado, reglas de limpieza, constructor de tablas de entrenamiento ML y exportador de paquetes de contexto LLM.",
  "dashboard.welcome_body_b":
    "Por ahora, ve a Seguridad en la barra lateral para activar autenticación multifactor.",

  // ----- Settings / Security ---------------------------------------------
  "settings.security.title": "Seguridad",
  "settings.security.subtitle": "Gestiona la autenticación multifactor y las sesiones activas.",

  "settings.mfa.disabled.title": "Autenticación multifactor",
  "settings.mfa.disabled.description":
    "Añade un segundo factor — un código de tu app de autenticación — requerido en cada inicio de sesión.",
  "settings.mfa.disabled.start": "Activar MFA",
  "settings.mfa.disabled.starting": "Activando…",

  "settings.mfa.scan.title": "Escanea este código QR",
  "settings.mfa.scan.description":
    "Abre Google Authenticator, Authy o 1Password y escanea. Después introduce el código de 6 dígitos.",
  "settings.mfa.scan.manual_prefix": "O introdúcelo manualmente:",
  "settings.mfa.scan.code_label": "Código de autenticación",
  "settings.mfa.scan.code_required": "Introduce el código de 6 dígitos de tu app.",
  "settings.mfa.scan.confirm": "Confirmar",
  "settings.mfa.scan.confirming": "Confirmando…",
  "settings.mfa.scan.cancel": "Cancelar",
  "settings.mfa.toast_enabled": "Autenticación multifactor activada.",
  "settings.mfa.failed_start": "No se pudo iniciar la activación de MFA.",
  "settings.mfa.failed_confirm": "No se pudo confirmar el código.",

  "settings.mfa.active.title": "La autenticación multifactor está activa",
  "settings.mfa.active.description":
    "Tu cuenta requiere un segundo factor en cada inicio de sesión.",

  "settings.mfa.disable.trigger": "Desactivar MFA",
  "settings.mfa.disable.title": "Desactivar autenticación multifactor",
  "settings.mfa.disable.description":
    "Confirma tu contraseña y un código actual del autenticador. Al desactivarla, los códigos de recuperación restantes también se invalidan.",
  "settings.mfa.disable.password_required": "La contraseña es obligatoria.",
  "settings.mfa.disable.code_required": "Introduce el código de 6 dígitos de tu app.",
  "settings.mfa.disable.submit": "Desactivar MFA",
  "settings.mfa.disable.submitting": "Desactivando…",
  "settings.mfa.disable.toast_success": "Autenticación multifactor desactivada.",
  "settings.mfa.disable.toast_failed": "No se pudo desactivar MFA.",

  "settings.recovery.title": "Guarda tus códigos de recuperación",
  "settings.recovery.description":
    "Guárdalos en un lugar seguro. Cada código sirve una sola vez. Son tu única forma de volver a entrar si pierdes acceso a tu app de autenticación. No se mostrarán de nuevo.",
  "settings.recovery.confirm": "Los he guardado",
  "settings.recovery.copied": "Códigos copiados.",
  "settings.recovery.copy_failed": "No se pudieron copiar. Selecciónalos y cópialos manualmente.",

  "settings.sessions.title": "Sesiones activas",
  "settings.sessions.description":
    "Cada sesión corresponde a un inicio de sesión. Revocar una sesión cierra ese navegador o dispositivo.",
  "settings.sessions.empty": "No hay sesiones activas.",
  "settings.sessions.failed_load": "No se pudieron cargar las sesiones.",
  "settings.sessions.this_session": "Esta sesión",
  "settings.sessions.unknown_device": "Dispositivo desconocido",
  "settings.sessions.unknown_ip": "desconocido",
  "settings.sessions.from": "Desde",
  "settings.sessions.started": "iniciada",
  "settings.sessions.expires": "expira",
  "settings.sessions.current": "Actual",
  "settings.sessions.revoke": "Revocar",
  "settings.sessions.revoked": "Sesión revocada.",
  "settings.sessions.revoke_failed": "No se pudo revocar.",

  // ----- Settings / Conexiones de IA (BYOK, slice G1) -------------------
  "nav.ai_connections": "Conexiones de IA",
  "settings.ai.title": "Conexiones de IA",
  "settings.ai.subtitle":
    "Registra las claves de tus proveedores de inteligencia artificial (OpenAI, Anthropic, Google, Ollama). Decide quién en tu equipo puede usar cada una.",
  "settings.ai.who_can_register":
    "Solo los administradores del workspace pueden registrar y compartir conexiones. Los miembros sólo verán las que tú compartas con ellos.",
  "settings.ai.not_admin.title": "No tienes permisos para esta sección",
  "settings.ai.not_admin.body":
    "Solo los administradores del workspace pueden gestionar las conexiones con proveedores de IA. Si necesitas usar el agente, pide a un admin que te dé acceso a una conexión.",

  "settings.ai.list.empty.title": "Aún no has registrado ninguna conexión",
  "settings.ai.list.empty.body":
    "Conecta un proveedor para que el agente pueda generar análisis y propuestas. Nosotros nunca vemos tu clave — se cifra antes de guardarse.",
  "settings.ai.list.empty.cta": "Nueva conexión",
  "settings.ai.list.new": "Nueva conexión",
  "settings.ai.list.col.nickname": "Nombre",
  "settings.ai.list.col.provider": "Proveedor",
  "settings.ai.list.col.model": "Modelo por defecto",
  "settings.ai.list.col.access": "Acceso",
  "settings.ai.list.col.last_test": "Último test",
  "settings.ai.list.col.actions": "",
  "settings.ai.list.never_tested": "Nunca probada",
  "settings.ai.list.test_ok": "Funciona",
  "settings.ai.list.test_error": "Falló",
  "settings.ai.list.load_failed": "No se pudieron cargar las conexiones.",

  // Field labels + helper text used both in the new-credential modal
  // and the edit modal.
  "settings.ai.field.nickname": "Nombre interno",
  "settings.ai.field.nickname_hint":
    "Cómo verás esta conexión en la lista (ej: \"OpenAI producción\").",
  "settings.ai.field.nickname_placeholder": "Ej: OpenAI producción",
  "settings.ai.field.provider": "Proveedor",
  "settings.ai.field.api_key": "Clave de API",
  "settings.ai.field.api_key_hint":
    "Se cifra antes de guardarse. Una vez guardada no se vuelve a mostrar — sólo se puede reemplazar por una nueva.",
  "settings.ai.field.api_key_placeholder": "Pega aquí tu clave",
  "settings.ai.field.api_key_rotate_placeholder":
    "Pega una nueva clave para rotar (déjala vacía para mantener la actual)",
  "settings.ai.field.api_key_docs": "¿Dónde la obtengo?",
  "settings.ai.field.model": "Modelo por defecto",
  "settings.ai.field.model_hint":
    "El modelo que el agente usará cuando elija esta conexión. Podrás cambiarlo por conversación más adelante.",
  "settings.ai.field.model_live": "Lista actualizada del proveedor",
  "settings.ai.field.model_hint_live":
    "Estos son los modelos a los que tu clave tiene acceso ahora mismo, según el proveedor.",
  "settings.ai.field.base_url": "URL del servidor",
  "settings.ai.field.base_url_hint":
    "Dirección donde está corriendo tu Ollama (ej: http://localhost:11434).",
  "settings.ai.field.base_url_placeholder": "http://localhost:11434",
  "settings.ai.field.access": "¿Quién en tu equipo puede usar esta conexión?",
  "settings.ai.field.access_admins_only": "Solo administradores",
  "settings.ai.field.access_admins_only_hint":
    "Únicamente owners y admins del workspace verán esta conexión.",
  "settings.ai.field.access_all_members": "Todos los miembros del workspace",
  "settings.ai.field.access_all_members_hint":
    "Cualquier persona del workspace podrá usarla al iniciar un chat.",
  "settings.ai.field.access_specific_members": "Personas específicas",
  "settings.ai.field.access_specific_members_hint":
    "Tú eliges quién puede usarla. Configura los miembros después de guardar.",

  // New-credential modal
  "settings.ai.new.title": "Nueva conexión de IA",
  "settings.ai.new.subtitle":
    "Elige un proveedor, pega la clave y decide quién puede usarla.",
  "settings.ai.new.choose_provider": "Elige un proveedor",
  "settings.ai.new.test_before_save": "Probar antes de guardar",
  "settings.ai.new.testing": "Probando…",
  "settings.ai.new.test_ok": "Conexión válida.",
  "settings.ai.new.test_failed": "La prueba falló: {error}",
  "settings.ai.new.submit": "Guardar conexión",
  "settings.ai.new.submitting": "Guardando…",
  "settings.ai.new.toast_success": "Conexión guardada.",
  "settings.ai.new.test_required":
    "Prueba la conexión antes de guardar para confirmar que la clave funciona.",
  "settings.ai.new.api_key_required": "Pega tu clave de API.",
  "settings.ai.new.base_url_required":
    "Indica la URL de tu servidor de Ollama.",
  "settings.ai.new.nickname_required": "Ponle un nombre a esta conexión.",

  // Edit modal
  "settings.ai.edit.title": "Editar conexión",
  "settings.ai.edit.subtitle":
    "Actualiza el nombre, el modelo por defecto o rota la clave. Para cambiar el proveedor, crea una nueva conexión.",
  "settings.ai.edit.submit": "Guardar cambios",
  "settings.ai.edit.submitting": "Guardando…",
  "settings.ai.edit.toast_success": "Conexión actualizada.",

  // Row actions
  "settings.ai.row.edit": "Editar",
  "settings.ai.row.test": "Probar",
  "settings.ai.row.testing": "Probando…",
  "settings.ai.row.test_ok": "Conexión válida.",
  "settings.ai.row.test_failed": "La prueba falló: {error}",
  "settings.ai.row.delete": "Eliminar",
  "settings.ai.row.share": "Gestionar acceso",
  "settings.ai.row.toast_deleted": "Conexión eliminada.",
  "settings.ai.row.confirm_delete":
    "¿Eliminar esta conexión? Los miembros que la estaban usando perderán acceso.",

  // Grants (specific_members) modal
  "settings.ai.grants.title": "Quién puede usar esta conexión",
  "settings.ai.grants.subtitle":
    "Sólo las personas que añadas aquí podrán elegirla al iniciar un chat.",
  "settings.ai.grants.add_placeholder": "Añadir un miembro…",
  "settings.ai.grants.empty": "Aún no le has dado acceso a nadie.",
  "settings.ai.grants.remove": "Quitar",
  "settings.ai.grants.granted": "Acceso concedido.",
  "settings.ai.grants.revoked": "Acceso revocado.",
  "settings.ai.grants.load_failed": "No se pudieron cargar los miembros.",
  "settings.ai.grants.no_more_members":
    "Todos los miembros del workspace ya tienen acceso.",

  // Member-access labels reused in the list table
  "settings.ai.access.admins_only": "Solo admins",
  "settings.ai.access.all_members": "Todo el equipo",
  "settings.ai.access.specific_members": "Personas específicas",

  // ----- Agent / Chat (slice G2.1 — agent-led) --------------------------
  "agent.next.title": "Tu asistente está listo",
  "agent.next.body":
    "El asistente vio tu dataset y el análisis. Cuando pulses Comenzar, te presentará lo que encontró y te ofrecerá opciones claras según lo que quieras hacer con estos datos.",
  "agent.next.cta": "Comenzar con la IA",
  "agent.next.starting": "Iniciando…",
  "agent.next.previous": "Conversaciones anteriores",
  "agent.no_creds.title": "No tienes ninguna conexión disponible",
  "agent.no_creds.admin":
    "Registra una conexión en \"Conexiones de IA\" para empezar a usar el asistente.",
  "agent.no_creds.member":
    "Pídele a un administrador del workspace que te dé acceso a una conexión de IA.",
  "agent.no_creds.cta": "Ir a Conexiones de IA",
  "agent.picker.title": "Elige una conexión de IA",
  "agent.picker.subtitle":
    "Tienes varias conexiones disponibles. ¿Cuál quieres usar para esta conversación?",
  "agent.picker.label": "Conexión",
  "agent.picker.submit": "Empezar",

  // Pending-action card (the [Aceptar / Rechazar] surface above a
  // visualization when the agent wants to mutate the data).
  "agent.pending.title": "El asistente quiere ejecutar esta acción",
  "agent.pending.accept": "Aceptar y ejecutar",
  "agent.pending.reject": "Rechazar",
  "agent.chat.title": "Conversación con el agente",
  "agent.chat.subtitle_prefix": "Sobre el dataset",
  "agent.chat.back": "Volver al dataset",
  "agent.chat.empty.title": "Aún no has dicho nada",
  "agent.chat.empty.body":
    "Pregunta por la calidad de tus datos, pide un resumen de las columnas, o describe la limpieza que necesitas.",
  "agent.chat.input_placeholder": "Escribe tu mensaje…",
  "agent.chat.send": "Enviar",
  "agent.chat.sending": "Pensando…",
  "agent.chat.you": "Tú",
  "agent.chat.agent": "Agente",
  "agent.chat.tokens": "{total} tokens",
  "agent.chat.load_failed": "No se pudo cargar la conversación.",
  "agent.chat.send_failed": "El agente no pudo responder. Intenta de nuevo.",
  "agent.chat.not_found": "Esta conversación no existe o no tienes acceso.",
  "agent.chat.delete": "Eliminar conversación",
  "agent.chat.confirm_delete":
    "¿Eliminar esta conversación? Se borran todos los mensajes.",
  "agent.chat.deleted": "Conversación eliminada.",
  "agent.list.title": "Conversaciones",
  "agent.list.empty": "Aún no has iniciado ninguna conversación sobre este dataset.",
  "agent.list.untitled": "Conversación sin título",
  "agent.list.with_provider": "con {provider}",
  "nav.conversations": "Conversaciones",
} as const;

export type DictionaryKey = keyof typeof es;

// English mirrors the Spanish dictionary one-for-one.
export const en: Record<DictionaryKey, string> = {
  "common.cancel": "Cancel",
  "common.save": "Save",
  "common.loading": "Loading…",
  "common.copy_all": "Copy all",
  "common.email": "Email",
  "common.password": "Password",
  "common.confirm_password": "Confirm password",
  "common.workspace": "Workspace",
  "common.workspace_name": "Workspace name",
  "common.code": "Code",
  "common.something_went_wrong": "Something went wrong. Try again.",
  "common.network_error": "Network error. Check your connection and try again.",

  "brand.name": "dataprep",
  "brand.version_note": "Built for modern data teams.",

  "theme.switch_to_dark": "Switch to dark mode",
  "theme.switch_to_light": "Switch to light mode",
  "theme.toggle": "Toggle theme",

  "locale.switch_to_english": "Switch to English",
  "locale.switch_to_spanish": "Switch to Spanish",

  "auth.layout.status_operational": "Status · Operational",
  "auth.layout.copyright": "© 2026 dataprep",
  "auth.layout.terms": "Terms",
  "auth.layout.privacy": "Privacy",
  "auth.layout.security_link": "Security",
  "auth.layout.status_page": "Status",

  "auth.login.workspace_eyebrow": "Workspace login",
  "auth.login.tenant_prefix": "Signing in to",
  "auth.login.tenant_default": "acme.dataprep.io",
  "auth.login.sso_google": "Continue with Google",
  "auth.login.sso_microsoft": "Continue with Microsoft",
  "auth.login.sso_saml": "Continue with SAML SSO",
  "auth.login.divider": "or continue with email",
  "auth.login.remember_device": "Remember this device",
  "auth.login.request_access": "New here? Request access",
  "auth.login.caps_lock": "Caps Lock is on",
  "auth.login.sso_not_configured": "{provider} isn't configured yet",
  "auth.login.sso_not_configured_sub":
    "Continue with email and password, or contact your workspace admin to enable SSO.",
  "auth.login.sso_error_sub":
    "Try again or use email and password. If the problem persists, contact support.",
  "auth.login.sso_error.not_configured": "SSO isn't configured on this server",
  "auth.login.sso_error.unsupported_provider": "Unsupported SSO provider",
  "auth.login.sso_error.missing_state": "OAuth session lost — start again",
  "auth.login.sso_error.state_mismatch": "Security check failed",
  "auth.login.sso_error.invalid_state": "OAuth session invalid or expired",
  "auth.login.sso_error.provider_mismatch": "Provider mismatch",
  "auth.login.sso_error.no_email": "Provider didn't return an email",
  "auth.login.sso_error.exchange_failed": "Provider rejected the request",
  "auth.login.sso_error.access_denied": "Provider denied access",
  "auth.login.sso_error.auth_accountinactiveerror": "Your account is deactivated",
  "auth.login.sso_error.unknown_error": "Something went wrong with SSO",

  "compliance.soc2": "SOC 2 Type II",
  "compliance.iso": "ISO 27001",
  "compliance.gdpr": "GDPR",
  "compliance.tls": "TLS 1.3",
  "compliance.soc2_tooltip": "Audited annually under SOC 2 Type II.",
  "compliance.iso_tooltip": "ISO/IEC 27001 certified — information security management.",
  "compliance.gdpr_tooltip": "Processing conforms to GDPR.",
  "compliance.tls_tooltip": "TLS 1.3 transport encryption on every connection.",

  "right.eyebrow": "Native integrations",
  "right.headline": "Your data stack, in one workspace.",
  "right.sub":
    "Connect any source. The agent profiles, proposes and cleans. You approve.",
  "right.testimonial_quote":
    "We cut data prep time by 80% for training our models.",
  "right.testimonial_author": "M. García",
  "right.testimonial_role": "Head of Data, Acme Inc.",
  "right.feature_one": "20+ native connectors",
  "right.feature_one_sub": "Postgres, Snowflake, BigQuery, S3.",
  "right.feature_two": "Automatic AI profiling",
  "right.feature_two_sub": "Types, nulls and anomalies detected.",
  "right.feature_three": "Ready for training",
  "right.feature_three_sub": "Training tables and context bundles.",
  "right.infra_eyebrow": "Global infrastructure",
  "right.infra_metric": "12 regions · 99.99% SLA",
  "right.infra_sub": "Per-workspace data residency.",

  "auth.login.eyebrow": "Sign in",
  "auth.login.title": "Welcome {accent}",
  "auth.login.title_accent": "back",
  "auth.login.subtitle": "Sign in to your dataprep workspace.",
  "auth.login.forgot": "Forgot password?",
  "auth.login.submit": "Sign in",
  "auth.login.submitting": "Signing in…",
  "auth.login.no_account": "New here?",
  "auth.login.create_account": "Create an account",
  "auth.login.email_required": "Enter a valid email address.",
  "auth.login.password_required": "Password is required.",

  "auth.register.eyebrow": "Get started",
  "auth.register.title": "Create your {accent}",
  "auth.register.title_accent": "workspace",
  "auth.register.subtitle":
    "You become the owner of a fresh workspace. Takes 30 seconds.",
  "auth.register.workspace_placeholder": "Acme Inc",
  "auth.register.password_hint":
    "At least 12 characters. A passphrase of three or four random words works well.",
  "auth.register.submit": "Create account",
  "auth.register.submitting": "Creating account…",
  "auth.register.toast_success": "Account created. Check your terminal for the verification link.",
  "auth.register.have_account": "Already have an account?",
  "auth.register.login_link": "Log in",
  "auth.register.password_too_short": "Password must be at least 12 characters long.",
  "auth.register.password_too_long": "Password is too long.",
  "auth.register.workspace_required": "Workspace name is required.",
  "auth.register.workspace_too_long": "Workspace name is too long.",

  "auth.verify.eyebrow": "One last step",
  "auth.verify.title": "Verify your email",
  "auth.verify.subtitle": "We sent a verification link to your inbox.",
  "auth.verify.idle":
    "We just sent you a link. In dev, the link is printed in the backend terminal — click it (or paste it) to verify.",
  "auth.verify.verifying": "Verifying your email…",
  "auth.verify.ok": "Your email is verified.",
  "auth.verify.error": "We could not verify this link.",
  "auth.verify.continue": "Continue to sign in",
  "auth.verify.back": "Back to sign in",
  "auth.verify.failed": "Verification failed.",

  "auth.mfa.eyebrow": "Step 2 of 2",
  "auth.mfa.title": "Two-factor authentication",
  "auth.mfa.subtitle": "Enter the 6-digit code from your authenticator app to finish signing in.",
  "auth.mfa.label_totp": "Authentication code",
  "auth.mfa.label_recovery": "Recovery code",
  "auth.mfa.toggle_to_recovery": "Use a recovery code instead",
  "auth.mfa.toggle_to_totp": "Use code from authenticator app",
  "auth.mfa.submit": "Verify",
  "auth.mfa.submitting": "Verifying…",
  "auth.mfa.code_required": "Enter a code.",
  "auth.mfa.code_too_long": "Code is too long.",
  "auth.mfa.code_charset": "Only digits, letters, hyphens and spaces.",

  "auth.forgot.eyebrow": "Recover access",
  "auth.forgot.title": "Reset your password",
  "auth.forgot.subtitle": "Enter your email and we'll send you a link to choose a new password.",
  "auth.forgot.submit": "Send reset link",
  "auth.forgot.submitting": "Sending…",
  "auth.forgot.confirmation":
    "If that email is registered, we've sent a password reset link. In dev, the link is printed in the backend terminal.",
  "auth.forgot.back": "Back to login",

  "auth.reset.eyebrow": "Set a new password",
  "auth.reset.title": "Choose a new password",
  "auth.reset.subtitle":
    "Pick a strong password — at least 12 characters. A passphrase works well.",
  "auth.reset.new_password": "New password",
  "auth.reset.submit": "Update password",
  "auth.reset.submitting": "Updating…",
  "auth.reset.toast_success": "Password updated. Please sign in.",
  "auth.reset.invalid_link": "Missing or invalid reset link.",
  "auth.reset.request_new": "Request a new link",
  "auth.reset.passwords_dont_match": "Passwords do not match.",
  "auth.reset.confirm_required": "Confirm your password.",

  "nav.dashboard": "Dashboard",
  "nav.datasets": "Data",
  "nav.security": "Security",
  "nav.logout": "Logout",
  "nav.workspace": "Workspace",
  "nav.logout_success": "Logged out.",
  "nav.logout_failed": "Logout failed.",

  "datasets.title": "Your data",
  "datasets.subtitle": "Upload files or connect a database to get started.",
  "datasets.upload_cta": "Upload file",
  "datasets.load_failed": "Failed to load datasets.",
  "datasets.empty.title": "No datasets yet",
  "datasets.empty.body":
    "Upload a CSV to begin. PostgreSQL, SQL Server, Parquet and Excel are coming soon.",
  "datasets.empty.cta": "Upload your first file",
  "datasets.col.name": "Name",
  "datasets.col.source": "Source",
  "datasets.col.visibility": "Visibility",
  "datasets.col.created": "Created",
  "datasets.visibility.private": "Private",
  "datasets.visibility.shared_workspace": "Whole workspace",
  "datasets.visibility.shared_specific": "Shared",

  "datasets.upload.title": "Upload a file",
  "datasets.upload.subtitle":
    "CSV, Parquet and Excel are supported. We auto-detect column types.",
  "datasets.upload.back": "Back",
  "datasets.upload.name_label": "Dataset name",
  "datasets.upload.name_placeholder": "Products",
  "datasets.upload.name_hint":
    "How it will appear in the list. Defaults to the file name.",
  "datasets.upload.file_label": "File",
  "datasets.upload.drop_here": "Drop your file here, or click to choose",
  "datasets.upload.drop_hint": "CSV, Parquet, Excel. Max size: 500 MB.",
  "datasets.upload.unsupported": "Unsupported format. We accept CSV, Parquet and Excel.",
  "datasets.upload.no_file": "Choose a file to upload.",
  "datasets.upload.no_name": "Give the dataset a name.",
  "datasets.upload.submit": "Upload and analyse",
  "datasets.upload.submitting": "Uploading…",
  "datasets.upload.toast_success": "Dataset created.",

  "datasets.detail.back": "Back to data",
  "datasets.detail.not_found": "We couldn't find this dataset.",
  "datasets.detail.load_failed": "Failed to load the dataset.",
  "datasets.detail.columns_title": "Detected columns ({count})",
  "datasets.detail.sample_title": "Sample ({count} rows)",
  "datasets.detail.col.name": "Column",
  "datasets.detail.col.type": "Type",
  "datasets.detail.col.sample": "Examples",

  "datasets.connect_cta": "Connect database",
  "datasets.empty.connect": "Connect a database",

  "sources.kind.postgres": "PostgreSQL",
  "sources.kind.mssql": "SQL Server",
  "sources.kind.mssql_azure": "Azure SQL",

  "sources.new.title": "Connect a database",
  "sources.new.subtitle":
    "We test the connection before saving. Credentials are encrypted at rest.",
  "sources.new.back": "Back",
  "sources.new.kind": "Database kind",
  "sources.new.name": "Name",
  "sources.new.name_placeholder": "Production · Postgres",
  "sources.new.host": "Host",
  "sources.new.port": "Port",
  "sources.new.database": "Database",
  "sources.new.user": "User",
  "sources.new.password": "Password",
  "sources.new.sslmode": "SSL mode",
  "sources.new.test": "Test connection",
  "sources.new.test_ok": "Connection successful.",
  "sources.new.test_failed": "Could not connect.",
  "sources.new.connect": "Connect and pick tables",
  "sources.new.created": "Source created.",
  "sources.new.fill_required": "Fill in the required fields.",

  "sources.tables.title": "Pick tables to import",
  "sources.tables.subtitle":
    "Each selected table becomes a dataset. We detect columns and types automatically.",
  "sources.tables.back": "Back to data",
  "sources.tables.filter": "Search by schema or name…",
  "sources.tables.select_all": "Select all",
  "sources.tables.deselect_all": "Deselect all",
  "sources.tables.col.schema": "Schema",
  "sources.tables.col.name": "Table",
  "sources.tables.col.rows": "Rows (estimated)",
  "sources.tables.empty": "No matching tables.",
  "sources.tables.import": "Import {count}",
  "sources.tables.imported": "Imported {count} tables as datasets.",
  "sources.tables.load_failed": "Failed to load tables.",

  "profile.title": "Quality analysis",
  "profile.run": "Run analysis",
  "profile.running": "Analysing…",
  "profile.empty": "No analysis has been run for this dataset yet.",
  "profile.failed": "Analysis failed.",
  "profile.row_count": "Rows",
  "profile.col.name": "Column",
  "profile.col.type": "Type",
  "profile.col.nulls": "Nulls",
  "profile.col.distinct": "Distinct",
  "profile.col.range": "Range",
  "profile.col.top": "Top values",

  "share.title": "Share",
  "share.visibility_label": "Who can see this dataset",
  "share.visibility.private": "Only me",
  "share.visibility.shared_workspace": "Whole workspace",
  "share.visibility.shared_specific": "Specific people",
  "share.add_user": "Add person",
  "share.add_user_placeholder": "Pick a member…",
  "share.no_grants": "You haven't shared with anyone yet.",
  "share.remove": "Remove",
  "share.updated": "Visibility updated.",
  "share.granted": "Access granted.",
  "share.revoked": "Access revoked.",

  "dashboard.greeting": "Hello, {email}",
  "dashboard.workspace_label": "Workspace:",
  "dashboard.welcome_title": "Welcome to dataprep",
  "dashboard.welcome_body_a":
    "Authentication is up and running. The data preparation features land in the next iterations: data source connectors, profiling, cleansing rules, ML training-table builder, and the LLM-context bundle exporter.",
  "dashboard.welcome_body_b":
    "For now, head to Security in the sidebar to set up multi-factor authentication.",

  "settings.security.title": "Security",
  "settings.security.subtitle": "Manage multi-factor authentication and active sessions.",

  "settings.mfa.disabled.title": "Multi-factor authentication",
  "settings.mfa.disabled.description":
    "Add a second factor — a code from an authenticator app — required at every sign-in.",
  "settings.mfa.disabled.start": "Set up MFA",
  "settings.mfa.disabled.starting": "Starting…",

  "settings.mfa.scan.title": "Scan this QR code",
  "settings.mfa.scan.description":
    "Open Google Authenticator, Authy, or 1Password and scan. Then enter the 6-digit code below.",
  "settings.mfa.scan.manual_prefix": "Or enter manually:",
  "settings.mfa.scan.code_label": "Authentication code",
  "settings.mfa.scan.code_required": "Enter the 6-digit code from your app.",
  "settings.mfa.scan.confirm": "Confirm",
  "settings.mfa.scan.confirming": "Confirming…",
  "settings.mfa.scan.cancel": "Cancel",
  "settings.mfa.toast_enabled": "Multi-factor authentication enabled.",
  "settings.mfa.failed_start": "Failed to start MFA setup.",
  "settings.mfa.failed_confirm": "Failed to confirm code.",

  "settings.mfa.active.title": "Multi-factor authentication is on",
  "settings.mfa.active.description": "Your account requires a second factor at every sign-in.",

  "settings.mfa.disable.trigger": "Disable MFA",
  "settings.mfa.disable.title": "Disable multi-factor authentication",
  "settings.mfa.disable.description":
    "Confirm your password and a current authenticator code. After disabling, any leftover recovery codes are also invalidated.",
  "settings.mfa.disable.password_required": "Password is required.",
  "settings.mfa.disable.code_required": "Enter the 6-digit code from your app.",
  "settings.mfa.disable.submit": "Disable MFA",
  "settings.mfa.disable.submitting": "Disabling…",
  "settings.mfa.disable.toast_success": "Multi-factor authentication disabled.",
  "settings.mfa.disable.toast_failed": "Failed to disable MFA.",

  "settings.recovery.title": "Save your recovery codes",
  "settings.recovery.description":
    "Store these somewhere safe. Each code works once. They're your only way back in if you lose access to your authenticator app. They will not be shown again.",
  "settings.recovery.confirm": "I've saved them",
  "settings.recovery.copied": "Recovery codes copied.",
  "settings.recovery.copy_failed": "Couldn't copy. Select and copy manually.",

  "settings.sessions.title": "Active sessions",
  "settings.sessions.description":
    "Each session corresponds to one login. Revoking a session signs out that browser / device.",
  "settings.sessions.empty": "No active sessions.",
  "settings.sessions.failed_load": "Failed to load sessions.",
  "settings.sessions.this_session": "This session",
  "settings.sessions.unknown_device": "Unknown device",
  "settings.sessions.unknown_ip": "unknown",
  "settings.sessions.from": "From",
  "settings.sessions.started": "started",
  "settings.sessions.expires": "expires",
  "settings.sessions.current": "Current",
  "settings.sessions.revoke": "Revoke",
  "settings.sessions.revoked": "Session revoked.",
  "settings.sessions.revoke_failed": "Failed to revoke.",

  // ----- Settings / AI connections (BYOK, slice G1) ---------------------
  "nav.ai_connections": "AI connections",
  "settings.ai.title": "AI connections",
  "settings.ai.subtitle":
    "Register the keys for your AI providers (OpenAI, Anthropic, Google, Ollama). Decide who on your team can use each one.",
  "settings.ai.who_can_register":
    "Only workspace admins can register and share connections. Members only see the ones you share with them.",
  "settings.ai.not_admin.title": "You don't have access to this section",
  "settings.ai.not_admin.body":
    "Only workspace admins can manage AI provider connections. If you need to use the agent, ask an admin to grant you access to a connection.",

  "settings.ai.list.empty.title": "You haven't registered any connections yet",
  "settings.ai.list.empty.body":
    "Connect a provider so the agent can generate analyses and proposals. We never see your key — it's encrypted before being stored.",
  "settings.ai.list.empty.cta": "New connection",
  "settings.ai.list.new": "New connection",
  "settings.ai.list.col.nickname": "Name",
  "settings.ai.list.col.provider": "Provider",
  "settings.ai.list.col.model": "Default model",
  "settings.ai.list.col.access": "Access",
  "settings.ai.list.col.last_test": "Last test",
  "settings.ai.list.col.actions": "",
  "settings.ai.list.never_tested": "Never tested",
  "settings.ai.list.test_ok": "Working",
  "settings.ai.list.test_error": "Failed",
  "settings.ai.list.load_failed": "Couldn't load connections.",

  "settings.ai.field.nickname": "Internal name",
  "settings.ai.field.nickname_hint":
    "How you'll see this connection in the list (e.g. \"OpenAI production\").",
  "settings.ai.field.nickname_placeholder": "E.g. OpenAI production",
  "settings.ai.field.provider": "Provider",
  "settings.ai.field.api_key": "API key",
  "settings.ai.field.api_key_hint":
    "Encrypted before storage. Once saved it's never shown again — only replaceable by a new one.",
  "settings.ai.field.api_key_placeholder": "Paste your key here",
  "settings.ai.field.api_key_rotate_placeholder":
    "Paste a new key to rotate (leave empty to keep the current one)",
  "settings.ai.field.api_key_docs": "Where do I get it?",
  "settings.ai.field.model": "Default model",
  "settings.ai.field.model_hint":
    "The model the agent will use when this connection is selected. You'll be able to override it per conversation later.",
  "settings.ai.field.model_live": "Live list from provider",
  "settings.ai.field.model_hint_live":
    "These are the models your key actually has access to right now, straight from the provider.",
  "settings.ai.field.base_url": "Server URL",
  "settings.ai.field.base_url_hint":
    "The address where your Ollama is running (e.g. http://localhost:11434).",
  "settings.ai.field.base_url_placeholder": "http://localhost:11434",
  "settings.ai.field.access": "Who on your team can use this connection?",
  "settings.ai.field.access_admins_only": "Admins only",
  "settings.ai.field.access_admins_only_hint":
    "Only workspace owners and admins will see this connection.",
  "settings.ai.field.access_all_members": "All workspace members",
  "settings.ai.field.access_all_members_hint":
    "Anyone in the workspace can use it when starting a chat.",
  "settings.ai.field.access_specific_members": "Specific people",
  "settings.ai.field.access_specific_members_hint":
    "You choose who can use it. Configure members after saving.",

  "settings.ai.new.title": "New AI connection",
  "settings.ai.new.subtitle":
    "Pick a provider, paste the key, decide who can use it.",
  "settings.ai.new.choose_provider": "Choose a provider",
  "settings.ai.new.test_before_save": "Test before saving",
  "settings.ai.new.testing": "Testing…",
  "settings.ai.new.test_ok": "Connection is valid.",
  "settings.ai.new.test_failed": "Test failed: {error}",
  "settings.ai.new.submit": "Save connection",
  "settings.ai.new.submitting": "Saving…",
  "settings.ai.new.toast_success": "Connection saved.",
  "settings.ai.new.test_required":
    "Test the connection before saving to confirm the key works.",
  "settings.ai.new.api_key_required": "Paste your API key.",
  "settings.ai.new.base_url_required":
    "Provide the URL of your Ollama server.",
  "settings.ai.new.nickname_required": "Give this connection a name.",

  "settings.ai.edit.title": "Edit connection",
  "settings.ai.edit.subtitle":
    "Update the name, default model, or rotate the key. To change provider, create a new connection.",
  "settings.ai.edit.submit": "Save changes",
  "settings.ai.edit.submitting": "Saving…",
  "settings.ai.edit.toast_success": "Connection updated.",

  "settings.ai.row.edit": "Edit",
  "settings.ai.row.test": "Test",
  "settings.ai.row.testing": "Testing…",
  "settings.ai.row.test_ok": "Connection is valid.",
  "settings.ai.row.test_failed": "Test failed: {error}",
  "settings.ai.row.delete": "Delete",
  "settings.ai.row.share": "Manage access",
  "settings.ai.row.toast_deleted": "Connection deleted.",
  "settings.ai.row.confirm_delete":
    "Delete this connection? Members who were using it will lose access.",

  "settings.ai.grants.title": "Who can use this connection",
  "settings.ai.grants.subtitle":
    "Only the people you add here will be able to pick it when starting a chat.",
  "settings.ai.grants.add_placeholder": "Add a member…",
  "settings.ai.grants.empty": "You haven't granted access to anyone yet.",
  "settings.ai.grants.remove": "Remove",
  "settings.ai.grants.granted": "Access granted.",
  "settings.ai.grants.revoked": "Access revoked.",
  "settings.ai.grants.load_failed": "Couldn't load members.",
  "settings.ai.grants.no_more_members":
    "Every workspace member already has access.",

  "settings.ai.access.admins_only": "Admins only",
  "settings.ai.access.all_members": "Whole team",
  "settings.ai.access.specific_members": "Specific people",

  // ----- Agent / Chat (slice G2.1 — agent-led) --------------------------
  "agent.next.title": "Your assistant is ready",
  "agent.next.body":
    "The assistant has looked at your dataset and its analysis. When you click Start, it'll walk you through what it found and offer clear options based on what you want to do with this data.",
  "agent.next.cta": "Start with the AI",
  "agent.next.starting": "Starting…",
  "agent.next.previous": "Previous conversations",
  "agent.no_creds.title": "You don't have any available connections",
  "agent.no_creds.admin":
    "Register a connection in \"AI connections\" to start using the assistant.",
  "agent.no_creds.member":
    "Ask a workspace admin to grant you access to an AI connection.",
  "agent.no_creds.cta": "Go to AI connections",
  "agent.picker.title": "Pick an AI connection",
  "agent.picker.subtitle":
    "You have multiple connections available. Which one should we use for this conversation?",
  "agent.picker.label": "Connection",
  "agent.picker.submit": "Start",

  "agent.pending.title": "The assistant wants to run this action",
  "agent.pending.accept": "Accept and run",
  "agent.pending.reject": "Reject",
  "agent.chat.title": "Conversation with the agent",
  "agent.chat.subtitle_prefix": "About dataset",
  "agent.chat.back": "Back to dataset",
  "agent.chat.empty.title": "You haven't said anything yet",
  "agent.chat.empty.body":
    "Ask about data quality, request a column summary, or describe the cleaning you need.",
  "agent.chat.input_placeholder": "Type your message…",
  "agent.chat.send": "Send",
  "agent.chat.sending": "Thinking…",
  "agent.chat.you": "You",
  "agent.chat.agent": "Agent",
  "agent.chat.tokens": "{total} tokens",
  "agent.chat.load_failed": "Couldn't load the conversation.",
  "agent.chat.send_failed": "The agent couldn't reply. Try again.",
  "agent.chat.not_found": "This conversation doesn't exist or you don't have access.",
  "agent.chat.delete": "Delete conversation",
  "agent.chat.confirm_delete":
    "Delete this conversation? All messages will be removed.",
  "agent.chat.deleted": "Conversation deleted.",
  "agent.list.title": "Conversations",
  "agent.list.empty": "You haven't started any conversations on this dataset yet.",
  "agent.list.untitled": "Untitled conversation",
  "agent.list.with_provider": "with {provider}",
  "nav.conversations": "Conversations",
};

export const dictionaries = { es, en } as const;
export type Locale = keyof typeof dictionaries;
export const LOCALES: Locale[] = ["es", "en"];
export const DEFAULT_LOCALE: Locale = "es";
