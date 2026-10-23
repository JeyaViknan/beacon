// "Add to Home Screen" tip: iOS only delivers Web Push to installed (standalone) web apps.

export const INSTALL_TIP_KEY = "beacon.installTipDismissed";

export interface InstallEnv {
  userAgent: string;
  platform: string;
  maxTouchPoints: number;
  standalone: boolean | undefined;
  displayModeStandalone: boolean;
  dismissed: boolean;
}

export function isIOS(env: Pick<InstallEnv, "userAgent" | "platform" | "maxTouchPoints">): boolean {
  if (/iPad|iPhone|iPod/.test(env.userAgent)) return true;
  // iPadOS 13+ reports itself as a Mac with touch.
  return env.platform === "MacIntel" && env.maxTouchPoints > 1;
}

export function shouldShowInstallTip(env: InstallEnv): boolean {
  if (env.dismissed) return false;
  if (!isIOS(env)) return false;
  return env.standalone !== true && !env.displayModeStandalone;
}

export function currentInstallEnv(): InstallEnv {
  let dismissed = false;
  try {
    dismissed = localStorage.getItem(INSTALL_TIP_KEY) === "1";
  } catch {
    dismissed = false;
  }
  const nav = navigator as Navigator & { standalone?: boolean };
  return {
    userAgent: nav.userAgent,
    platform: nav.platform,
    maxTouchPoints: nav.maxTouchPoints,
    standalone: nav.standalone,
    displayModeStandalone: window.matchMedia?.("(display-mode: standalone)").matches ?? false,
    dismissed,
  };
}

export function dismissInstallTip(): void {
  try {
    localStorage.setItem(INSTALL_TIP_KEY, "1");
  } catch {
    // Private mode: the tip simply shows again next time.
  }
}
