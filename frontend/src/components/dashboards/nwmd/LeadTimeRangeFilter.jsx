import { useMemo, useState } from "react";
import { Form } from "react-bootstrap";
import { formatLeadTimeBinLabel, sortLeadTimeBins } from "./leadTimeBins";

const LeadTimeRangeSlider = ({
  leadTimeBins,
  selectedLeadTimeBin,
  onCommit,
}) => {
  const initialIndex = Math.max(
    leadTimeBins.findIndex((bin) => bin === selectedLeadTimeBin),
    0,
  );
  const [pendingLeadTimeIndex, setPendingLeadTimeIndex] =
    useState(initialIndex);

  const pendingLeadTimeBin = leadTimeBins[pendingLeadTimeIndex];
  const selectedLeadTimeLabel = pendingLeadTimeBin
    ? formatLeadTimeBinLabel(pendingLeadTimeBin)
    : "No lead time bins available";

  const commitPendingSelection = () => {
    const nextBin = leadTimeBins[pendingLeadTimeIndex];
    if (nextBin && nextBin !== selectedLeadTimeBin) {
      void onCommit(nextBin);
    }
  };

  return (
    <>
      <Form.Label className="small fw-bold">
        Lead time (hours): {selectedLeadTimeLabel}
      </Form.Label>
      <Form.Range
        min={0}
        max={Math.max(leadTimeBins.length - 1, 0)}
        step={1}
        disabled={leadTimeBins.length === 0}
        value={pendingLeadTimeIndex}
        onChange={(e) => {
          setPendingLeadTimeIndex(Number(e.target.value));
        }}
        onPointerUp={commitPendingSelection}
        onKeyUp={commitPendingSelection}
      />
    </>
  );
};

const LeadTimeRangeFilter = ({
  leadTimeBins,
  selectedLeadTimeBin,
  onCommit,
}) => {
  const orderedLeadTimeBins = useMemo(
    () => sortLeadTimeBins(Array.isArray(leadTimeBins) ? leadTimeBins : []),
    [leadTimeBins],
  );
  const selectedLeadTimeIndex = orderedLeadTimeBins.findIndex(
    (bin) => bin === selectedLeadTimeBin,
  );
  const selectedLeadTimeBinValue =
    orderedLeadTimeBins[
      selectedLeadTimeIndex >= 0 ? selectedLeadTimeIndex : 0
    ] || selectedLeadTimeBin;
  const resetKey = `${orderedLeadTimeBins.join("|")}:${
    selectedLeadTimeBinValue || "none"
  }`;

  return (
    <LeadTimeRangeSlider
      key={resetKey}
      leadTimeBins={orderedLeadTimeBins}
      selectedLeadTimeBin={selectedLeadTimeBinValue}
      onCommit={onCommit}
    />
  );
};

export default LeadTimeRangeFilter;
