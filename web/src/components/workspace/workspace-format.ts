export function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  return `${Math.round(value / 102.4) / 10} KB`;
}

export function formatPrerequisite(value: string): string {
  return value.replaceAll("_", " ");
}
