import { useState } from "react";
import { currentInstallEnv, dismissInstallTip, shouldShowInstallTip } from "../lib/install";
import { isNativeApp } from "../lib/platform";
import { Icon } from "./Icon";

export function InstallTip() {
  const [visible, setVisible] = useState(() => !isNativeApp() && shouldShowInstallTip(currentInstallEnv()));
  if (!visible) return null;
  return (
    <div className="flex items-start gap-3 rounded-[26px] bg-cell py-3 pr-2 pl-4" role="note">
      <span className="pt-0.5 text-tint">
        <Icon name="square.and.arrow.up" className="size-7" />
      </span>
      <p className="flex-1 pt-1 text-subhead">
        Tap <strong>Share</strong>, then <strong>Add to Home Screen</strong>, to get alerts on this iPhone.
      </p>
      <button
        type="button"
        aria-label="Dismiss tip"
        className="flex size-9 flex-none items-center justify-center rounded-full text-label-3 active:opacity-60"
        onClick={() => {
          dismissInstallTip();
          setVisible(false);
        }}
      >
        <Icon name="xmark" className="size-5" />
      </button>
    </div>
  );
}
