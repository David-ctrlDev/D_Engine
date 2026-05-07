import { Suspense } from "react";

import { ResetPasswordForm } from "@/components/auth/reset-password-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function ResetPasswordPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Choose a new password</CardTitle>
        <CardDescription>
          Pick a strong password — at least 12 characters. A passphrase works well.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* useSearchParams() requires a Suspense boundary in the App Router. */}
        <Suspense>
          <ResetPasswordForm />
        </Suspense>
      </CardContent>
    </Card>
  );
}
