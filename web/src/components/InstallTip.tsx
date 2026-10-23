import { useState } from "react";
import { currentInstallEnv, dismissInstallTip, shouldShowInstallTip } from "../lib/install";
import { CloseIcon, ShareIcon } from "./Icons";

export function InstallTip() {
  const [visible, setVisible] = useState(() => shouldShowInstallTip(currentInstallEnv()));
  if (!visible) return null;
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-line bg-surface-2 p-3 text-sm" role="note">
      <ShareIcon className="mt-0.5 h-5 w-5 flex-none text-muted" />
      <p className="flex-1">
        Tap <strong>Share</strong> → <strong>Add to Home Screen</strong> to get alerts on this iPhone.
      </p>
      <button
        type="button"
        aria-label="Dismiss tip"
        className="-m-2 flex h-11 w-11 flex-none items-center justify-center text-muted"
        onClick={() => {
          dismissInstallTip();
          setVisible(false);
        }}
      >
        <CloseIcon className="h-4 w-4" />
      </button>
    </div>
  );
}
