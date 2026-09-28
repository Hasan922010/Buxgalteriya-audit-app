"use client";

import React, { useState } from "react";
import { downloadWithAuth } from "@/lib/auth";

interface AuthDownloadLinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  href: string;
  fallbackName?: string;
}

/**
 * Looks like a normal download link but fetches the file with the bearer token,
 * because a plain <a href> cannot send the Authorization header.
 */
export function AuthDownloadLink({ href, fallbackName, children, className, ...rest }: AuthDownloadLinkProps) {
  const [busy, setBusy] = useState(false);

  const handleClick = async (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      await downloadWithAuth(href, fallbackName);
    } catch (err: any) {
      alert(err.message || "Faylni yuklab bo'lmadi");
    } finally {
      setBusy(false);
    }
  };

  return (
    <a
      {...rest}
      href={href}
      onClick={handleClick}
      aria-busy={busy}
      className={`${className ?? ""} ${busy ? "opacity-60 pointer-events-none" : ""}`}
    >
      {children}
    </a>
  );
}

export default AuthDownloadLink;
