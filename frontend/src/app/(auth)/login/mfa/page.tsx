import { MFAForm } from "@/components/auth/mfa-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginMFAPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Two-factor authentication</CardTitle>
        <CardDescription>
          Enter the 6-digit code from your authenticator app to finish signing in.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <MFAForm />
      </CardContent>
    </Card>
  );
}
