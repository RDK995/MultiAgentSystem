import { API_BASE_URL } from "../../shared/api/runClient";

type ReportLinkProps = {
  artifactPath: string | null;
};

export function ReportLink({ artifactPath }: ReportLinkProps) {
  if (!artifactPath) {
    return <span>Report link appears after generation.</span>;
  }

  const href = `${API_BASE_URL}/api/artifact/file?path=${encodeURIComponent(artifactPath)}`;
  return (
    <a className="report-agent-link" href={href} target="_blank" rel="noreferrer">
      Open full analyzed-items report
    </a>
  );
}
