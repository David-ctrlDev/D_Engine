/**
 * Title + subtitle block reused at the top of every auth page.
 *
 * Lives outside a Card on purpose — the (auth) layout already provides
 * the panel framing; nesting another bordered Card looks heavy.
 */

export function AuthPageHeader({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-8 space-y-2">
      {eyebrow && (
        <p className="text-muted-foreground text-xs uppercase tracking-[0.18em]">{eyebrow}</p>
      )}
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      {subtitle && <p className="text-muted-foreground text-sm">{subtitle}</p>}
    </div>
  );
}
