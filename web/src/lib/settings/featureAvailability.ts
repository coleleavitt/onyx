interface EnterpriseFeatureState {
  isLoading: boolean;
  error: unknown;
  enabled: boolean | undefined;
}

export function enterpriseFeaturesAvailable({
  isLoading,
  error,
  enabled,
}: EnterpriseFeatureState): boolean {
  return !isLoading && !error && enabled !== false;
}
