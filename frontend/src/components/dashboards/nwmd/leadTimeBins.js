export const parseDurationToHours = (duration) => {
  if (typeof duration !== "string" || !duration.startsWith("P")) return null;

  const match = duration.match(
    /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/,
  );
  if (!match) return null;

  const days = Number(match[1] || 0);
  const hours = Number(match[2] || 0);
  const minutes = Number(match[3] || 0);
  const seconds = Number(match[4] || 0);

  return days * 24 + hours + minutes / 60 + seconds / 3600;
};

export const getLeadTimeBinBounds = (leadTimeBin) => {
  if (typeof leadTimeBin !== "string") return null;

  const [minDuration, maxDuration] = leadTimeBin.split("_");
  const minHours = parseDurationToHours(minDuration);
  const maxHours = parseDurationToHours(maxDuration);

  if (minHours === null || maxHours === null) return null;

  return {
    minHours: Math.round(minHours),
    maxHours: Math.round(maxHours),
  };
};

export const formatLeadTimeBinLabel = (leadTimeBin) => {
  const bounds = getLeadTimeBinBounds(leadTimeBin);
  if (!bounds) return leadTimeBin || "";

  return `${bounds.minHours} to <${bounds.maxHours}`;
};

export const sortLeadTimeBins = (bins = []) =>
  [...bins].sort((leftBin, rightBin) => {
    const leftBounds = getLeadTimeBinBounds(leftBin);
    const rightBounds = getLeadTimeBinBounds(rightBin);

    if (leftBounds && rightBounds) {
      if (leftBounds.minHours !== rightBounds.minHours) {
        return leftBounds.minHours - rightBounds.minHours;
      }

      return leftBounds.maxHours - rightBounds.maxHours;
    }

    if (leftBounds) return -1;
    if (rightBounds) return 1;

    return String(leftBin).localeCompare(String(rightBin));
  });
