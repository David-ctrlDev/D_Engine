/**
 * Title + subtitle block reused at the top of every auth page.
 *
 * The h1 is set in Fraunces (the serif loaded for the editorial
 * hero) so the form column inherits the same typographic voice as
 * the marketing panel — without restyling every input.
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
        <p className="text-muted-foreground text-xs tracking-[0.22em] uppercase">{eyebrow}</p>
      )}
      <h1
        className="text-3xl leading-[1.05] font-medium tracking-tight sm:text-[2.25rem]"
        style={{ fontFamily: "var(--font-fraunces), Georgia, serif" }}
      >
        {title}
      </h1>
      {subtitle && <p className="text-muted-foreground text-sm">{subtitle}</p>}
    </div>
  );
}
