import { Link } from "react-router-dom";
import { EmptyState } from "../components/Feedback";
import { Screen } from "../components/Layout";

export default function NotFoundPage() {
  return (
    <Screen title="Not Found" large={false} back="/">
      <EmptyState
        symbol="link"
        title="Page Not Found"
        action={
          <Link to="/" className="inline-flex h-9 items-center rounded-full bg-fill-3 px-4 text-subhead font-semibold text-tint active:opacity-60">
            Back to Status
          </Link>
        }
      >
        This page doesn't exist.
      </EmptyState>
    </Screen>
  );
}
