import { useWindowDimensions } from 'react-native';

/**
 * One breakpoint hook, so every component agrees on what "narrow" means.
 *
 * Both rails are the same width. They carry different content, but a layout
 * whose two edges differ by 36 px reads as a mistake rather than as a
 * hierarchy, and symmetry costs nothing here.
 *
 * 196 px is deliberately tight: it holds a section label and an item title at
 * 12 px, and anything longer is handled by horizontal scrolling inside the
 * rail rather than by widening it or truncating with an ellipsis. Giving the
 * centre column the space is the right trade -- the rails are for getting
 * somewhere, the centre is what you came to read.
 */
export const RAIL_W = 196;

export function useLayout() {
  const { width, height } = useWindowDimensions();

  // 196 + 196 + ~600 centre + gutters. Below that the right rail folds first,
  // because navigation must survive longer than context.
  const wide = width >= 1120;
  const medium = width >= 780 && width < 1120;
  const compact = width < 780;

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
    contentMax: wide ? 900 : 760,
    hit: compact ? 46 : 34,
    gutter: compact ? 12 : 18,
  };
}
