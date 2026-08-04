/**
 * Maps RGBW/tunable-white roles to 0-based DMX universe offsets.
 *
 * Uses the device's real DMX slot descriptions (RDM SLOT_DESCRIPTION, fetched
 * via the `slots` module) when they clearly identify each channel. Falls back
 * to the conventional R,G,B,W (or warm/cool) repeating pattern tiled across
 * the whole 512-channel universe when no usable descriptions are available.
 */

const UNIVERSE_SIZE = 512

export interface RgbwOffsets {
  red: number
  green: number
  blue: number
  /** -1 if no white slot was identified (e.g. a plain RGB fixture). */
  white: number
}

export interface TwOffsets {
  warm: number
  cool: number
}

function findOffset(descriptions: string[], startAddress: number, pattern: RegExp): number | null {
  for (let index = 0; index < descriptions.length; index += 1) {
    const offset = startAddress - 1 + index
    if (offset >= UNIVERSE_SIZE) break
    if (pattern.test(descriptions[index].toLowerCase())) return offset
  }
  return null
}

export function resolveRgbwOffsets(
  slotDescriptions: string[] | null,
  startAddress: number,
): RgbwOffsets[] {
  if (slotDescriptions && slotDescriptions.length > 0) {
    const red = findOffset(slotDescriptions, startAddress, /\bred\b/)
    const green = findOffset(slotDescriptions, startAddress, /\bgreen\b/)
    const blue = findOffset(slotDescriptions, startAddress, /\bblue\b/)
    const white = findOffset(slotDescriptions, startAddress, /\bwhite\b/)
    if (red !== null && green !== null && blue !== null) {
      return [{ red, green, blue, white: white ?? -1 }]
    }
  }

  // No usable slot descriptions - tile the classic R,G,B,W pattern across the whole universe.
  const groups: RgbwOffsets[] = []
  for (let base = 0; base + 3 < UNIVERSE_SIZE; base += 4) {
    groups.push({ red: base, green: base + 1, blue: base + 2, white: base + 3 })
  }
  return groups
}

export function resolveTwOffsets(slotDescriptions: string[] | null, startAddress: number): TwOffsets[] {
  if (slotDescriptions && slotDescriptions.length > 0) {
    const warm = findOffset(slotDescriptions, startAddress, /warm/)
    const cool = findOffset(slotDescriptions, startAddress, /cool|cold/)
    if (warm !== null && cool !== null) {
      return [{ warm, cool }]
    }
  }

  // No usable slot descriptions - tile warm/cool pairs across the whole universe.
  const groups: TwOffsets[] = []
  for (let base = 0; base + 1 < UNIVERSE_SIZE; base += 2) {
    groups.push({ warm: base, cool: base + 1 })
  }
  return groups
}
