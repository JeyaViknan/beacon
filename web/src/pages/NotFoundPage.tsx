import { Link } from "react-router-dom";
import { PageHeader } from "../components/Layout";

export default function NotFoundPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Not found" back="/" />
      <p className="text-muted">This page doesn't exist.</p>
      <Link to="/" className="font-semibold underline">
        Back to status
      </Link>
    </div>
  );
}
