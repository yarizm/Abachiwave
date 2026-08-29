import { ReactNode } from "react";

import { WorkspaceProvider } from "./workspace-provider";
import { WorkspaceShell } from "./workspace-shell";

export default function ProjectWorkspaceLayout({ children }: { children: ReactNode }) {
  return (
    <WorkspaceProvider>
      <WorkspaceShell>{children}</WorkspaceShell>
    </WorkspaceProvider>
  );
}
