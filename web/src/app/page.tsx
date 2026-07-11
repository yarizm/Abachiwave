import { LogIn } from "lucide-react";
import Link from "next/link";

export default function HomePage() {
  return (
    <section className="panel">
      <h1>Local development login</h1>
      <p>
        Authentication is intentionally a placeholder in Milestone 0. Use the local projects
        workspace to verify the API, database, and frontend integration.
      </p>
      <Link className="button" href="/projects">
        <LogIn aria-hidden="true" size={18} />
        Open projects
      </Link>
    </section>
  );
}
