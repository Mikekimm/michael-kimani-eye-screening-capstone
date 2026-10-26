/**
 * Instant, on-device quality hints shown before upload. They mirror the server's checks
 * (backend/app/ml/quality.py) but never block: the server's quality gate is the authority.
 */
export interface QualityHints {
  width: number;
  height: number;
  brightness: number;
  sharpness: number;
  hints: string[];
}

const SIZE = 256;

/** Brightness = mean grey level; sharpness = variance of the 4-neighbour Laplacian. */
export function assessGray(gray: Float32Array, width: number, height: number): Pick<QualityHints, "brightness" | "sharpness"> {
  let sum = 0;
  for (const value of gray) sum += value;
  const brightness = sum / gray.length;

  let lapSum = 0;
  let lapSq = 0;
  let n = 0;
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const i = y * width + x;
      const lap = gray[i - width]! + gray[i + width]! + gray[i - 1]! + gray[i + 1]! - 4 * gray[i]!;
      lapSum += lap;
      lapSq += lap * lap;
      n++;
    }
  }
  const mean = n ? lapSum / n : 0;
  return { brightness, sharpness: n ? lapSq / n - mean * mean : 0 };
}

export function hintsFor(width: number, height: number, brightness: number, sharpness: number): string[] {
  const hints: string[] = [];
  if (Math.min(width, height) < 224) hints.push("The photo is small. Use the camera's full resolution if possible.");
  if (brightness < 20) hints.push("The photo is very dark. Improve the lighting or the lens contact.");
  if (brightness > 235) hints.push("The photo is very bright. Reduce glare or flash.");
  if (sharpness < 20) hints.push("The photo looks blurry. Hold steady and retake if you can.");
  return hints;
}

export async function analyseImage(file: Blob): Promise<QualityHints> {
  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = SIZE;
  canvas.height = SIZE;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("Canvas is not supported on this device.");
  context.drawImage(bitmap, 0, 0, SIZE, SIZE);
  const { data } = context.getImageData(0, 0, SIZE, SIZE);
  const gray = new Float32Array(SIZE * SIZE);
  for (let i = 0; i < gray.length; i++) {
    gray[i] = 0.299 * data[i * 4]! + 0.587 * data[i * 4 + 1]! + 0.114 * data[i * 4 + 2]!;
  }
  const { brightness, sharpness } = assessGray(gray, SIZE, SIZE);
  const result = { width: bitmap.width, height: bitmap.height, brightness, sharpness,
    hints: hintsFor(bitmap.width, bitmap.height, brightness, sharpness) };
  bitmap.close();
  return result;
}
