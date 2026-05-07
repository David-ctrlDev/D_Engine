"use client";

/**
 * /settings/security — orchestrates the MFA setup flow, recovery codes
 * dialog, MFA disable confirmation, and active sessions table.
 *
 * MFA "is on" state is currently inferred from setup-then-confirm of the
 * dialog within this page lifetime. Future iteration: expose
 * ``mfa_enabled`` on /auth/me so refreshes know the truth.
 */

import { useState } from "react";

import { DisableMFADialog } from "@/components/settings/disable-mfa-dialog";
import { MFASetupCard } from "@/components/settings/mfa-setup-card";
import { RecoveryCodesDialog } from "@/components/settings/recovery-codes-dialog";
import { SessionsTable } from "@/components/settings/sessions-table";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export default function SecurityPage() {
  const [mfaActive, setMfaActive] = useState(false);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [showCodes, setShowCodes] = useState(false);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Security</h1>
        <p className="text-muted-foreground text-sm">
          Manage multi-factor authentication and active sessions.
        </p>
      </div>

      <Separator />

      {mfaActive ? (
        <Card>
          <CardHeader>
            <CardTitle>Multi-factor authentication is on</CardTitle>
            <CardDescription>
              Your account requires a second factor at every sign-in.
            </CardDescription>
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
