import { Suspense } from "react";

import { VerifyEmailFlow } from "@/components/auth/verify-email-flow";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function VerifyEmailPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Verify your email</CardTitle>
      </CardHeader>
      <CardContent>
        <Suspense>
          <VerifyEmailFlow />
        </Suspense>
      </CardContent>
    </Card>
  );
}
