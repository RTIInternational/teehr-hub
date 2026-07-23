export const groupSecondaryTimeseriesItems = (items = []) => {
  const grouped = new Map();

  items.forEach((item) => {
    const key = [
      item.series_type,
      item.primary_location_id,
      item.secondary_location_id,
      item.reference_time,
      item.configuration_name,
      item.variable_name,
      item.unit_name,
      item.member,
    ]
      .map((value) => String(value ?? ""))
      .join("|");

    if (!grouped.has(key)) {
      grouped.set(key, {
        series_type: item.series_type,
        primary_location_id: item.primary_location_id,
        secondary_location_id: item.secondary_location_id,
        reference_time: item.reference_time,
        configuration_name: item.configuration_name,
        variable_name: item.variable_name,
        unit_name: item.unit_name,
        member: item.member,
        timeseries: [],
      });
    }

    grouped.get(key).timeseries.push({
      value_time: item.value_time,
      value: item.value,
    });
  });

  return Array.from(grouped.values());
};

export const groupPrimaryTimeseriesItems = (items = []) => {
  const grouped = new Map();

  items.forEach((item) => {
    const key = [
      item.series_type,
      item.primary_location_id,
      item.configuration_name,
      item.variable_name,
      item.unit_name,
      item.member,
    ]
      .map((value) => String(value ?? ""))
      .join("|");

    if (!grouped.has(key)) {
      grouped.set(key, {
        series_type: item.series_type,
        primary_location_id: item.primary_location_id,
        configuration_name: item.configuration_name,
        variable_name: item.variable_name,
        unit_name: item.unit_name,
        member: item.member,
        timeseries: [],
      });
    }

    grouped.get(key).timeseries.push({
      value_time: item.value_time,
      value: item.value,
    });
  });

  return Array.from(grouped.values());
};
