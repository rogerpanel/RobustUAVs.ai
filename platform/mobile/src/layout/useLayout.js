import { useWindowDimensions } from 'react-native';

/**
 * One breakpoint hook, so every component agrees on what "narrow" means.
 *
 * The thresholds are chosen from what has to fit rather than from device
 * marketing widths: the left rail needs 232 px to hold a section label plus an
 * item title without wrapping, the right rail 260 px, and the centre column is
 * unreadable below about 340 px. 1180 and 820 fall out of those sums.
 *
 * Returned as booleans rather than a single enum because most call sites ask
 * one question ("do I show the rail?"), and a string comparison invites the
 * mistake of testing for the wrong tier.
 */
export const LEFT_RAIL_W = 232;
export const RIGHT_RAIL_W = 268;

export function useLayout() {
  const { width, height } = useWindowDimensions();

  const wide = width >= 1180;    // both rails pinned open
  const medium = width >= 820 && width < 1180;  // left rail pinned, right on demand
  const compact = width < 820;   // neither pinned; bottom tabs carry navigation

  return {
    width,
    height,
    wide,
    medium,
    compact,
    /** Rails that are permanently visible at this size. */
    showLeftRail: wide || medium,
    showRightRail: wide,
    /** Bottom tabs exist only where there is no left rail to replace them. */
    showTabs: compact,
    /**
     * Centre column cap. Long-form text past ~72 characters per line is
     * measurably harder to scan, and on a 27-inch monitor an uncapped column
     * is exactly that.
     */
    contentMax: wide ? 860 : 720,
    /** Touch targets grow on phones; pointer targets need less. */
    hit: compact ? 46 : 36,
    gutter: compact ? 14 : 20,
  };
}
