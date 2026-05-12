/**
 * Card-internal heading. Deliberately small.
 *
 * The page tagline outside the card is the visual hero now. Inside
 * the card we just identify the action ("Iniciar sesión",
 * "Crea tu workspace") with restrained typography so the two
 * headlines don't fight for the eye.
 *
 * Hierarchy:
 *   eyebrow  — 10 px mono, uppercase, very wide tracking, muted
 *   title    — 1.2 / 1.25 rem semibold, neutral foreground
 *              (no gradient text; the optional accent word renders
 *               in a solid brand violet only)
 *   subtitle — 12.5 px, muted, kept to 1-2 lines
 */

export function AuthPageHeader({
  eyebrow,
  title,
  accent,
  subtitle,
}: {
  eyebrow?: string;
  title: string;
  accent?: string;
  subtitle?: string;
}) {
  const parts = accent && title.includes("{accent}") ? title.split("{accent}") : null;

  return (
    <div className="mb-5 space-y-1 text-center">
      {eyebrow && (
        <p className="font-mono text-[10px] tracking-[0.22em] text-zinc-500 uppercase">
          {eyebrow}
        </p>
      )}
      <h1 className="text-[1.2rem] leading-[1.2] font-semibold tracking-tight text-zinc-50 sm:text-[1.25rem]">
        {parts ? (
          <>
            {parts[0]}
            <span className="text-indigo-300">{accent}</span>
            {parts[1]}
          </>
        ) : (
          title
        )}
      </h1>
      {subtitle && (
        <p className="mx-auto max-w-[280px] text-[12px] leading-snug text-zinc-400">{subtitle}</p>
      )}
    </div>
  );
}
