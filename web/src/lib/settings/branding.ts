export interface BrandAccentVariables {
  "--theme-primary-04": string;
  "--theme-primary-05": string;
  "--theme-primary-06": string;
}

function mixHexColor(hex: string, target: number, weight: number): string {
  const channels = [1, 3, 5].map((offset) =>
    Number.parseInt(hex.slice(offset, offset + 2), 16)
  );
  const mixed = channels.map((channel) =>
    Math.round(channel * (1 - weight) + target * weight)
      .toString(16)
      .padStart(2, "0")
  );
  return `#${mixed.join("")}`;
}

export function getBrandAccentVariables(
  accentColor: string | null | undefined
): BrandAccentVariables | null {
  if (!accentColor || !/^#[0-9a-f]{6}$/i.test(accentColor)) {
    return null;
  }

  return {
    "--theme-primary-04": mixHexColor(accentColor, 255, 0.12),
    "--theme-primary-05": accentColor,
    "--theme-primary-06": mixHexColor(accentColor, 0, 0.15),
  };
}
