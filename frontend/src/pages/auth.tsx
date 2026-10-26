import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, ShieldCheck } from "lucide-react";
import { forwardRef, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { HOME_FOR, hasConsented, recordConsent } from "@/components/AppShell";
import { Disclaimer, describeError } from "@/components/feedback";
import { Button, Card, FieldError, Input, Label } from "@/components/ui/primitives";
import { useAuth } from "@/hooks/useAuth";

export const loginSchema = z.object({
  email: z.string().trim().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

export const signupSchema = z.object({
  full_name: z.string().trim().min(2, "Enter your full name."),
  email: z.string().trim().email("Enter a valid email address."),
  password: z.string().min(8, "Use at least 8 characters.").max(128),
});

function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-4 px-4 py-8">
      <div className="flex flex-col items-center gap-2 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground"><Eye aria-hidden /></span>
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-sm text-muted-foreground">Retinal screening and referral support for primary health centres</p>
      </div>
      {children}
      <Disclaimer />
    </main>
  );
}

// forwardRef so React Hook Form's register() ref reaches the real <input>.
const PasswordInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { invalid: boolean }>(
  ({ id, invalid, ...props }, ref) => {
    const [visible, setVisible] = useState(false);
    return (
      <div className="relative">
        <Input ref={ref} id={id} type={visible ? "text" : "password"} aria-invalid={invalid} className="pr-12" {...props} />
        <button type="button" onClick={() => setVisible((v) => !v)} aria-label={visible ? "Hide password" : "Show password"}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-muted-foreground">
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    );
  },
);
PasswordInput.displayName = "PasswordInput";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });
  const { errors, isSubmitting } = form.formState;

  if (user) return <Navigate to={HOME_FOR[user.role]} replace />;

  const onSubmit = form.handleSubmit(async ({ email, password }) => {
    setServerError(null);
    try {
      const me = await login(email, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(hasConsented() ? from ?? HOME_FOR[me.role] : "/consent", { replace: true });
    } catch (error) {
      setServerError(describeError(error));
    }
  });

  return (
    <AuthLayout title="Sign in">
      <Card className="p-4">
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="username" aria-invalid={!!errors.email}
              aria-describedby="email-error" {...form.register("email")} />
            <FieldError id="email-error" message={errors.email?.message} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="password">Password</Label>
            <PasswordInput id="password" autoComplete="current-password" invalid={!!errors.password}
              aria-describedby="password-error" {...form.register("password")} />
            <FieldError id="password-error" message={errors.password?.message} />
          </div>
          {serverError && <p role="alert" className="text-sm text-destructive">{serverError}</p>}
          <Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Signing in..." : "Sign in"}</Button>
        </form>
      </Card>
      <p className="text-center text-sm">New health worker? <Link to="/signup" className="font-medium text-primary underline">Create an account</Link></p>
    </AuthLayout>
  );
}

export function SignupPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof signupSchema>>({ resolver: zodResolver(signupSchema), defaultValues: { full_name: "", email: "", password: "" } });
  const { errors, isSubmitting } = form.formState;

  if (user) return <Navigate to={HOME_FOR[user.role]} replace />;

  const onSubmit = form.handleSubmit(async (values) => {
    setServerError(null);
    try {
      await register(values);
      navigate("/consent", { replace: true });
    } catch (error) {
      setServerError(describeError(error));
    }
  });

  return (
    <AuthLayout title="Create account">
      <Card className="p-4">
        <p className="mb-3 text-sm text-muted-foreground">
          New accounts are health worker accounts. Specialist and administrator access is granted by an administrator.
        </p>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="full_name">Full name</Label>
            <Input id="full_name" autoComplete="name" aria-invalid={!!errors.full_name} aria-describedby="name-error" {...form.register("full_name")} />
            <FieldError id="name-error" message={errors.full_name?.message} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} aria-describedby="email-error" {...form.register("email")} />
            <FieldError id="email-error" message={errors.email?.message} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="password">Password</Label>
            <PasswordInput id="password" autoComplete="new-password" invalid={!!errors.password} aria-describedby="password-error" {...form.register("password")} />
            <FieldError id="password-error" message={errors.password?.message} />
          </div>
          {serverError && <p role="alert" className="text-sm text-destructive">{serverError}</p>}
          <Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Creating account..." : "Create account"}</Button>
        </form>
      </Card>
      <p className="text-center text-sm">Already registered? <Link to="/login" className="font-medium text-primary underline">Sign in</Link></p>
    </AuthLayout>
  );
}

export function ConsentPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [checked, setChecked] = useState(false);
  if (!user) return <Navigate to="/login" replace />;

  return (
    <AuthLayout title="Before you start">
      <Card className="flex flex-col gap-3 p-4 text-sm">
        <p className="flex items-center gap-2 font-medium"><ShieldCheck aria-hidden className="h-5 w-5 text-primary" />How to use this tool safely</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>It gives <strong>screening support</strong>, not a diagnosis. A specialist confirms every referral.</li>
          <li>Only diabetic retinopathy has a trained model. Glaucoma and cataract show "Model not available yet".</li>
          <li>The severity band is an <strong>estimate</strong> from the model score, not a clinical grade.</li>
          <li>Use patient codes, not names. Only capture images with the patient's consent.</li>
          <li>Offline, photos are saved on this device and analysed after they sync.</li>
        </ul>
        <label className="flex items-start gap-2">
          <input type="checkbox" className="mt-1 h-4 w-4" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
          I understand and will follow local referral guidance.
        </label>
        <Button disabled={!checked} onClick={() => { recordConsent(); navigate(HOME_FOR[user.role], { replace: true }); }}>Continue</Button>
      </Card>
    </AuthLayout>
  );
}
