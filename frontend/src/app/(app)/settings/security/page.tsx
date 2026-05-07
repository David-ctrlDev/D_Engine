"use client";

import { useState } from "react";

import { DisableMFADialog } from "@/components/settings/disable-mfa-dialog";
import { MFASetupCard } from "@/components/settings/mfa-setup-card";
import { RecoveryCodesDialog } from "@/components/settings/recovery-codes-dialog";
import { SessionsTable } from "@/components/settings/sessions-table";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useT } from "@/lib/i18n/provider";

export default function SecurityPage() {
  const t = useT();
  const [mfaActive, setMfaActive] = useState(false);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [showCodes, setShowCodes] = useState(false);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("settings.security.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("settings.security.subtitle")}</p>
      </div>

      <Separator />

      {mfaActive ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("settings.mfa.active.title")}</CardTitle>
            <CardDescription>{t("settings.mfa.active.description")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <DisableMFADialog
              onDisabled={() => {
                setMfaActive(false);
                setRecoveryCodes([]);
              }}
            />
          </CardContent>
        </Card>
      ) : (
        <MFASetupCard
          onConfirmed={(codes) => {
            setMfaActive(true);
            setRecoveryCodes(codes);
            setShowCodes(true);
          }}
        />
      )}

      <SessionsTable />

      <RecoveryCodesDialog
        open={showCodes}
        codes={recoveryCodes}
        onClose={() => setShowCodes(false)}
      />
    </div>
  );
}
