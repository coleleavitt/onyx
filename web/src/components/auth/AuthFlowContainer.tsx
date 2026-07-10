"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import { useSettings } from "@/lib/settings/hooks";
import { Logo } from "@/lib/app/components";

export default function AuthFlowContainer({
  children,
  authState,
  footerContent,
}: AuthFlowContainerProps) {
  const { enterprise, appName } = useSettings();
  const backgroundStyle: CSSProperties = {
    backgroundColor: enterprise?.login_background_color ?? undefined,
    backgroundImage: enterprise?.login_background_url
      ? `url("${enterprise.login_background_url.replaceAll('"', "%22")}")`
      : undefined,
    backgroundPosition: "center",
    backgroundSize: "cover",
  };

  return (
    <div
      className="p-4 flex flex-col items-center justify-center min-h-screen bg-background"
      style={backgroundStyle}
    >
      <div className="w-full max-w-md flex items-start flex-col bg-background-tint-00 rounded-16 shadow-lg shadow-box-02 p-6">
        <Logo folded size={44} />
        <div className="w-full mt-3">{children}</div>
        {authState === "login" && (
          <div className="text-sm pt-6 text-center w-full text-text-03 mainUiBody mx-auto">
            {footerContent ?? (
              <>
                New to {appName}?{" "}
                <Link
                  href="/auth/signup"
                  className="text-text-05 mainUiAction underline transition-colors duration-200"
                >
                  Create an Account
                </Link>
              </>
            )}
          </div>
        )}
        {authState === "signup" && (
          <div className="text-sm pt-6 text-center w-full text-text-03 mainUiBody mx-auto">
            Already have an account?{" "}
            <Link
              href="/auth/login?autoRedirectToSignup=false"
              className="text-text-05 mainUiAction underline transition-colors duration-200"
            >
              Sign In
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

interface AuthFlowContainerProps {
  children: React.ReactNode;
  authState?: "signup" | "login" | "join";
  footerContent?: React.ReactNode;
}
