/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_VAPID_PUBLIC_KEY?: string;
  readonly VITE_APP_VERSION?: string;
  readonly VITE_MOCK?: string;
  /** Absolute origin of the API for the native app, e.g. https://dxxxx.cloudfront.net ("" = same origin). */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
