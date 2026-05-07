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

  // ----- Hero (auth marketing panel) -------------------------------------
  "hero.eyebrow": "Plataforma de datos y machine learning",
  "hero.headline_a": "De los datos al modelo,",
  "hero.headline_b": "y del modelo al producto",
  "hero.headline_c": "",
  "hero.subtitle":
    "Ingesta, perfilado, limpieza, entrenamiento, evaluación y servicio — todo en una sola plataforma. ML clásico y LLMs en el mismo lugar, versionado y aislado por workspace.",
  "hero.status_pill": "Beta · Construido en abierto",
  "hero.sample_run": "el ciclo de extremo a extremo",
  "hero.node.source": "Fuente",
  "hero.node.profile": "Perfilar",
  "hero.node.train": "Entrenar",
  "hero.node.serve": "Servir",
  "hero.feature.any_source.title": "Conecta cualquier fuente",
  "hero.feature.any_source.body": "PostgreSQL, MongoDB, S3, CSV, Parquet.",
  "hero.feature.profiled.title": "Perfila, limpia y valida",
  "hero.feature.profiled.body": "Tipos, relaciones y anomalías automáticas.",
  "hero.feature.versioned.title": "Entrena y evalúa modelos",
  "hero.feature.versioned.body": "ML clásico, deep learning y agentes LLM.",
  "hero.feature.ml_llm.title": "Despliega en producción",
  "hero.feature.ml_llm.body": "Sirve modelos y LLMs versionados y reproducibles.",

  // ----- Auth layout -----------------------------------------------------
  "auth.layout.footer": "v0 · plataforma multi-tenant de preparación de datos",

  // ----- Login -----------------------------------------------------------
  "auth.login.eyebrow": "Iniciar sesión",
  "auth.login.title": "Bienvenido de nuevo",
  "auth.login.subtitle": "Inicia sesión en tu espacio de trabajo de dataprep.",
  "auth.login.forgot": "¿Olvidaste tu contraseña?",
  "auth.login.submit": "Iniciar sesión",
  "auth.login.submitting": "Iniciando sesión…",
  "auth.login.no_account": "¿Eres nuevo?",
  "auth.login.create_account": "Crea una cuenta",
  "auth.login.email_required": "Introduce un correo electrónico válido.",
  "auth.login.password_required": "La contraseña es obligatoria.",

  // ----- Register --------------------------------------------------------
  "auth.register.eyebrow": "Empieza ahora",
  "auth.register.title": "Crea tu espacio de trabajo",
  "auth.register.subtitle":
    "Regístrate para empezar a preparar datos. Te conviertes en propietario de un espacio de trabajo nuevo.",
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
    "Acepta CSV. Detectamos los tipos de columna automáticamente. Próximamente: Parquet y Excel.",
  "datasets.upload.back": "Volver",
  "datasets.upload.name_label": "Nombre del dataset",
  "datasets.upload.name_placeholder": "Productos",
  "datasets.upload.name_hint":
    "Cómo aparecerá en la lista. Por defecto usamos el nombre del archivo.",
  "datasets.upload.file_label": "Archivo",
  "datasets.upload.drop_here": "Arrastra tu CSV aquí, o haz clic para elegir",
  "datasets.upload.drop_hint": "Solo CSV por ahora. Tamaño máximo: 500 MB.",
  "datasets.upload.unsupported": "Formato no soportado. Por ahora solo aceptamos CSV.",
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

  "hero.eyebrow": "Data and machine learning platform",
  "hero.headline_a": "From data to model,",
  "hero.headline_b": "from model to product",
  "hero.headline_c": "",
  "hero.subtitle":
    "Ingest, profile, clean, train, evaluate and serve — all on one platform. Classic ML and LLMs together, versioned and workspace-isolated.",
  "hero.status_pill": "Beta · Built in the open",
  "hero.sample_run": "the end-to-end loop",
  "hero.node.source": "Source",
  "hero.node.profile": "Profile",
  "hero.node.train": "Train",
  "hero.node.serve": "Serve",
  "hero.feature.any_source.title": "Connect any source",
  "hero.feature.any_source.body": "PostgreSQL, MongoDB, S3, CSV, Parquet.",
  "hero.feature.profiled.title": "Profile, clean and validate",
  "hero.feature.profiled.body": "Types, relationships, anomalies — automatic.",
  "hero.feature.versioned.title": "Train and evaluate models",
  "hero.feature.versioned.body": "Classic ML, deep learning and LLM agents.",
  "hero.feature.ml_llm.title": "Deploy to production",
  "hero.feature.ml_llm.body": "Serve versioned, reproducible models and LLMs.",

  "auth.layout.footer": "v0 · multi-tenant data preparation platform",

  "auth.login.eyebrow": "Sign in",
  "auth.login.title": "Welcome back",
  "auth.login.subtitle": "Sign in to your dataprep workspace.",
  "auth.login.forgot": "Forgot password?",
  "auth.login.submit": "Sign in",
  "auth.login.submitting": "Signing in…",
  "auth.login.no_account": "New here?",
  "auth.login.create_account": "Create an account",
  "auth.login.email_required": "Enter a valid email address.",
  "auth.login.password_required": "Password is required.",

  "auth.register.eyebrow": "Get started",
  "auth.register.title": "Create your workspace",
  "auth.register.subtitle":
    "Sign up to start preparing data. You become the owner of a fresh workspace.",
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
    "CSV is supported. We auto-detect column types. Parquet and Excel coming soon.",
  "datasets.upload.back": "Back",
  "datasets.upload.name_label": "Dataset name",
  "datasets.upload.name_placeholder": "Products",
  "datasets.upload.name_hint":
    "How it will appear in the list. Defaults to the file name.",
  "datasets.upload.file_label": "File",
  "datasets.upload.drop_here": "Drop your CSV here, or click to choose",
  "datasets.upload.drop_hint": "CSV only for now. Max size: 500 MB.",
  "datasets.upload.unsupported": "Unsupported format. Only CSV for now.",
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
};

export const dictionaries = { es, en } as const;
export type Locale = keyof typeof dictionaries;
export const LOCALES: Locale[] = ["es", "en"];
export const DEFAULT_LOCALE: Locale = "es";
