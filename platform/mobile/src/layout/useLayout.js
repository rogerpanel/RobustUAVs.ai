import { useWindowDimensions } from 'react-native';

/**
 * One breakpoint hook, so every component agrees on what "narrow" means.
 *
 * Both rails are 150 px, matching robustidps.ai. That is narrow enough that
 * many labels overflow, which is the point: the rails scroll horizontally, so
 * an overflowing label is reachable rather than clipped, and the centre column
 * keeps the width. At 196 px the two rails together ate 392 px of a 1280 px
 * screen -- nearly a third of it -- for navigation nobody reads while working.
 *
 * They are the same width on both sides. A layout whose two edges differ by a
 * few dozen pixels reads as a mistake rather than as a hierarchy.
 */
export const RAIL_W = 150;

export function useLayout() {
  const { width, height } = useWindowDimensions();

  // 150 + 150 + ~640 centre + gutters. Below that the right rail folds first,
  // because navigation must survive longer than context.
  const wide = width >= 1040;
  const medium = width >= 720 && width < 1040;
  const compact = width < 720;

  // Phones in landscape are short, not narrow: a 58 px tab bar plus a 46 px
  // header leaves too little for content, so the header collapses first.
  const shortViewport = height < 480;

  return {
    width,
    height,
    wide,
    medium,
    compact,
    shortViewport,
    showLeftRail: wide || medium,
    showRightRail: wide,
    showTabs: compact,
    contentMax: wide ? 980 : 820,
    hit: compact ? 46 : 34,
    gutter: compact ? 12 : 18,
  };
}
